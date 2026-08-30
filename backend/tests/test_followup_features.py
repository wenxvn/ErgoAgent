import hashlib
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent import answer_question
from app.db import AnalysisRun, Base, EvidenceFrame, FrameObservation, RiskEvent, Worker, new_task
from app.report import write_report
from app.tracking import CentroidTracker
from app.reba import score_reba
from app.detector import detect_person_boxes
from app.baselines import load_manifest


def test_centroid_tracker_keeps_ids_and_handles_misses():
    tracker = CentroidTracker(max_distance=20, max_missed=1)
    assert tracker.update([(10, 10), (100, 100)], 0) == ["person-1", "person-2"]
    assert tracker.update([(14, 12), (96, 103)], 1) == ["person-1", "person-2"]
    assert tracker.update([(18, 15)], 2) == ["person-1"]
    assert tracker.update([], 3) == []
    assert tracker.update([], 4) == []
    assert tracker.update([(19, 16)], 5) == ["person-3"]

    grace = CentroidTracker(max_distance=1, max_missed=3, single_track_grace=True)
    assert grace.update([(0, 0)], 0) == ["person-1"]
    assert grace.update([], 1) == []
    assert grace.update([(100, 100)], 2) == ["person-1"]


def test_report_writes_html_and_json_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report.DATA_ROOT", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    task = new_task("unsafe <video>.mp4")
    db.add(task)
    db.flush()
    run = AnalysisRun(task_id=task.id, attempt=1, status="running", model_summary={"name": "MediaPipe Pose", "version": "0.10.21"}, ruleset_version="reba-lite-0.1")
    db.add(run)
    db.commit()

    write_report(db, run, {"summary": {"frames": 3, "detected_frames": 2, "peak_reba": 4}, "risk_events": [{"event_id": "evt-1", "start_ms": 0, "end_ms": 100, "peak_score": 8}]})
    db.commit()
    artifacts = {item.kind: item for item in run.artifacts}
    assert set(artifacts) == {"report", "report_json"}
    for artifact in artifacts.values():
        path = tmp_path / artifact.storage_path
        content = path.read_bytes()
        assert path.is_file()
        assert artifact.size_bytes == len(content)
        assert artifact.sha256 == hashlib.sha256(content).hexdigest()
    assert "unsafe &lt;video&gt;.mp4" in (tmp_path / artifacts["report"].storage_path).read_text(encoding="utf-8")
    assert json.loads((tmp_path / artifacts["report_json"].storage_path).read_text(encoding="utf-8"))["run_id"] == run.id


def test_agent_uses_highest_event_and_citations(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    task = new_task("sample.mp4")
    db.add(task)
    db.flush()
    run = AnalysisRun(task_id=task.id, attempt=1, status="succeeded", model_summary={"peak_reba": 9, "mean_confidence": 0.55}, ruleset_version="reba-lite-0.1")
    db.add(run)
    db.flush()
    worker = Worker(run_id=run.id, source_track_id="person-1", first_frame=0, last_frame=20, confidence=0.55)
    db.add(worker)
    db.flush()
    low = RiskEvent(run_id=run.id, worker_id=worker.id, start_frame=1, end_frame=2, start_ms=40, end_ms=80, peak_score=8, mean_score=8, body_region="arms", repetition_count=1, confidence=0.55, details={})
    high = RiskEvent(run_id=run.id, worker_id=worker.id, start_frame=10, end_frame=12, start_ms=400, end_ms=480, peak_score=9, mean_score=8.5, body_region="trunk", repetition_count=1, confidence=0.55, details={})
    db.add_all([low, high])
    db.flush()
    evidence = EvidenceFrame(run_id=run.id, event_id=high.id, worker_id=worker.id, frame_index=11, storage_path=f"evidence/{run.id}/frame-000011.jpg", sha256="a" * 64, reason="threshold")
    db.add(evidence)
    db.add(FrameObservation(run_id=run.id, worker_id=worker.id, frame_index=11, timestamp_ms=440, bbox={}, pose_2d={}, confidence=0.55, angles={"left_knee": {"degrees": 80, "confidence": 0.55, "source_keypoints": ["left_hip", "left_knee", "left_ankle"]}}, reba={"score": 9}))
    db.commit()

    result = answer_question(db, run.id, "查看证据和关节角度")
    assert "REBA 9" in result["answer"]
    assert any(item.get("event_id") == high.id for item in result["citations"])
    assert any(item.get("evidence_id") == evidence.id and item.get("frame_index") == 11 for item in result["citations"])
    assert any(item.get("type") == "frame_observation" and item.get("frame_index") == 11 for item in result["citations"])
    assert {call["tool"] for call in result["tool_calls"]} >= {"inspect_risk_event", "get_joint_angles"}


def test_standard_reba_proxy_is_bounded_and_auditable():
    result = score_reba({"trunk_flexion": 55, "left_knee": 80, "left_elbow": 140}, 0.55)
    assert 1 <= result["score"] <= 15
    assert result["risk_level"] in {"negligible", "low", "medium", "high", "very_high"}
    assert result["rule_version"] == "reba-standard-proxy-0.2"
    assert {"score_a", "score_b", "score_c", "load", "coupling", "activity"} <= result["component_scores"].keys()


def test_baseline_manifest_records_external_blockers():
    manifest = load_manifest()
    assert manifest["reference"]["status"] == "executed"
    names = {item["name"] for item in manifest["candidates"]}
    assert names == {"REBAPose", "AutoPostureCV"}
    assert all(item["status"].startswith("blocked_") for item in manifest["candidates"])


def test_hog_detector_is_optional_and_returns_structured_boxes():
    frame = type("Frame", (), {"shape": (240, 320, 3)})()
    assert detect_person_boxes(frame, type("CV2", (), {})(), mode="mediapipe") == []

    class FakeHog:
        def setSVMDetector(self, _):
            pass

        def detectMultiScale(self, _image, **_kwargs):
            return ([(0, 0, 80, 160), (4, 4, 80, 160), (180, 0, 70, 150)], [1.2, 1.0, 0.8])

    class FakeCV2:
        HOGDescriptor = FakeHog

        @staticmethod
        def HOGDescriptor_getDefaultPeopleDetector():
            return object()

    boxes = detect_person_boxes(frame, FakeCV2(), mode="hog")
    assert len(boxes) == 2
    assert all({"x", "y", "width", "height", "detector_confidence"} <= item.keys() for item in boxes)
