from __future__ import annotations

import hashlib
import math
import os
import subprocess
from pathlib import Path
from typing import Any

from .config import DATA_ROOT, PREVIEW_TARGET_FPS
from .db import AnalysisRun, AnalysisTask, EvidenceFrame, FrameObservation, ResultArtifact, RiskEvent, RunComponent, VideoAsset, Worker, utcnow
from .storage import resolve_safe
from .tracking import CentroidTracker
from .detector import detect_person_boxes, detector_mode
from .reba import score_reba

KEYPOINTS = {
    "nose": 0, "left_shoulder": 11, "right_shoulder": 12, "left_elbow": 13,
    "right_elbow": 14, "left_wrist": 15, "right_wrist": 16, "left_hip": 23,
    "right_hip": 24, "left_knee": 25, "right_knee": 26, "left_ankle": 27,
    "right_ankle": 28, "left_foot": 31, "right_foot": 32,
}

SKELETON = (
    ("nose", "left_shoulder"), ("nose", "right_shoulder"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_shoulder", "right_shoulder"), ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"), ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
)


def _draw_annotation(frame: Any, bbox: dict[str, float], points: dict[str, tuple[float, float, float]],
                     track_id: str, score: float, risk_level: str, cv2: Any) -> None:
    """Draw annotations that remain legible in both 1080p and 4K exports."""
    height, width = frame.shape[:2]
    scale = max(1.0, min(width, height) / 1080)
    color = (36, 76, 224) if score >= 8 else (34, 156, 84)
    outline = (12, 20, 35)
    line_width = max(3, round(4 * scale))
    point_radius = max(5, round(7 * scale))
    # Draw the skeleton twice so the colored stroke has contrast on bright footage.
    for start, end in SKELETON:
        first, second = points.get(start), points.get(end)
        if not first or not second or first[2] < 0.3 or second[2] < 0.3:
            continue
        p1 = (round(first[0]), round(first[1])); p2 = (round(second[0]), round(second[1]))
        cv2.line(frame, p1, p2, outline, line_width + max(3, round(3 * scale)), cv2.LINE_AA)
        cv2.line(frame, p1, p2, color, line_width, cv2.LINE_AA)
    for point in points.values():
        if point[2] < 0.3:
            continue
        center = (round(point[0]), round(point[1]))
        cv2.circle(frame, center, point_radius + max(2, round(2 * scale)), outline, -1, cv2.LINE_AA)
        cv2.circle(frame, center, point_radius, color, -1, cv2.LINE_AA)
    x1 = max(0, round(bbox["x"])); y1 = max(0, round(bbox["y"]))
    x2 = min(width - 1, round(bbox["x"] + bbox["width"])); y2 = min(height - 1, round(bbox["y"] + bbox["height"]))
    cv2.rectangle(frame, (x1, y1), (x2, y2), outline, line_width + max(3, round(3 * scale)), cv2.LINE_AA)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, line_width, cv2.LINE_AA)
    label = f"{track_id}  REBA {score:g}  {risk_level}"
    font_scale = max(0.7, 0.72 * scale)
    text_width, text_height = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, max(2, round(2 * scale)))[0]
    label_x = min(max(0, x1), max(0, width - text_width - line_width * 2))
    label_y = y1 - max(8, round(12 * scale))
    if label_y - text_height < 0:
        label_y = min(height - line_width, y1 + text_height + max(10, round(12 * scale)))
    padding = max(6, round(8 * scale))
    cv2.rectangle(frame, (label_x, label_y - text_height - padding), (label_x + text_width + padding * 2, label_y + padding // 2), outline, -1)
    cv2.putText(frame, label, (label_x + padding, label_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), max(2, round(2 * scale)), cv2.LINE_AA)


def _write_progress_preview(frame: Any, target: Path, cv2: Any) -> None:
    """Publish a compact preview atomically so readers never see a partial JPEG."""
    max_width = 1280
    preview = frame
    if frame.shape[1] > max_width:
        ratio = max_width / frame.shape[1]
        preview = cv2.resize(frame, (max_width, max(1, round(frame.shape[0] * ratio))), interpolation=cv2.INTER_AREA)
    temporary = target.with_name(f".{target.stem}.tmp.jpg")
    if cv2.imwrite(str(temporary), preview, [cv2.IMWRITE_JPEG_QUALITY, 82]):
        os.replace(temporary, target)

def _angle(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float | None:
    ba = (a[0] - b[0], a[1] - b[1]); bc = (c[0] - b[0], c[1] - b[1])
    den = math.hypot(*ba) * math.hypot(*bc)
    if den == 0: return None
    cosv = max(-1.0, min(1.0, (ba[0] * bc[0] + ba[1] * bc[1]) / den))
    return round(math.degrees(math.acos(cosv)), 1)

def _reba(angles: dict[str, float | None], confidence: float) -> dict[str, Any]:
    return score_reba(angles, confidence)

def _point(landmarks: Any, index: int, width: int, height: int) -> tuple[float, float, float]:
    p = landmarks[index]
    return (float(p.x * width), float(p.y * height), float(max(0, min(1, p.visibility))))


def _update_progress(
    db, run: AnalysisRun, *, stage: str, current_frame: int | None = None,
    total_frames: int | None = None, detected_frames: int | None = None,
    peak_reba: float | None = None, commit: bool = False,
) -> None:
    task = db.get(AnalysisTask, run.task_id)
    if task is None:
        return
    task.progress_stage = stage
    if current_frame is not None:
        task.progress_current_frame = current_frame
    if total_frames is not None:
        task.progress_total_frames = total_frames
    if detected_frames is not None:
        task.progress_detected_frames = detected_frames
    if peak_reba is not None:
        task.progress_peak_reba = peak_reba
    task.updated_at = utcnow()
    if commit:
        db.commit()

def analyze_video(run: AnalysisRun, video: VideoAsset, db) -> dict[str, Any]:
    try:
        import cv2
        import mediapipe as mp
    except Exception as exc:
        raise RuntimeError("vision_dependencies_missing: install opencv-python, mediapipe and numpy") from exc

    source = resolve_safe(video.storage_path)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened(): raise RuntimeError("video_open_failed: unable to open uploaded video")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0); height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25); fps = fps if fps > 0 else 25
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    out_dir = Path(DATA_ROOT) / "results" / run.id; out_dir.mkdir(parents=True, exist_ok=True)
    annotated = out_dir / "annotated.mp4"
    annotated_source = out_dir / "annotated-source.mp4"
    progress_preview = out_dir / "progress.jpg"
    preview_every = max(1, round(fps / max(1.0, PREVIEW_TARGET_FPS)))
    if width <= 0 or height <= 0:
        capture.release()
        raise RuntimeError("video_metadata_invalid: uploaded video has no frame dimensions")
    writer = cv2.VideoWriter(str(annotated_source), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("annotated_video_open_failed: unable to create result video")
    # Scale the pixel-space association threshold with the source resolution.
    # A fixed threshold fragments the same person in 4K footage when pose boxes
    # move by more than a few hundred pixels between adjacent frames.
    _update_progress(db, run, stage="detecting_pose", current_frame=0, total_frames=total_frames, detected_frames=0, peak_reba=0, commit=True)
    tracker = CentroidTracker(max_distance=max(width, height) * 0.2, max_missed=max(10, round(fps * 2)), single_track_grace=True)
    workers_by_track: dict[str, Worker] = {}
    frame_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    evidence_candidates: list[tuple[int, str, float, Any, dict[str, Any]]] = []
    # Cropped multi-person inputs are independent images; sharing temporal
    # tracking state between crops can make landmarks jump from one worker to
    # another. The verified default keeps MediaPipe's temporal smoothing.
    pose = mp.solutions.pose.Pose(static_image_mode=detector_mode() in {"hog", "opencv-hog"}, model_complexity=1, enable_segmentation=False, min_detection_confidence=0.5, min_tracking_confidence=0.5)
    index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok: break
            boxes = detect_person_boxes(frame, cv2)
            pose_results: list[tuple[dict[str, float], Any, int, int]] = []
            if boxes:
                for detected in boxes:
                    x = max(0, min(width - 1, round(detected["x"])))
                    y = max(0, min(height - 1, round(detected["y"])))
                    w = max(1, min(width - x, round(detected["width"])))
                    h = max(1, min(height - y, round(detected["height"])))
                    crop = frame[y:y + h, x:x + w]
                    result = pose.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
                    if result.pose_landmarks:
                        pose_results.append((detected, result.pose_landmarks.landmark, x, y))
            if not pose_results:
                result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if result.pose_landmarks:
                    pose_results.append(({"x": 0.0, "y": 0.0, "width": float(width), "height": float(height), "detector_confidence": 0.0}, result.pose_landmarks.landmark, 0, 0))
            track_centers: list[tuple[float, float]] = []
            prepared: list[tuple[dict[str, float], dict[str, tuple[float, float, float]]]] = []
            for detected, landmarks, origin_x, origin_y in pose_results:
                crop_width = max(1, round(detected["width"])) if detected["width"] else width
                crop_height = max(1, round(detected["height"])) if detected["height"] else height
                pts = {name: _point(landmarks, idx, crop_width, crop_height) for name, idx in KEYPOINTS.items()}
                pts = {name: (value[0] + origin_x, value[1] + origin_y, value[2]) for name, value in pts.items()}
                bbox = {"x": min(v[0] for v in pts.values()), "y": min(v[1] for v in pts.values()), "width": max(v[0] for v in pts.values()) - min(v[0] for v in pts.values()), "height": max(v[1] for v in pts.values()) - min(v[1] for v in pts.values())}
                bbox["detector_confidence"] = round(float(detected.get("detector_confidence", 0.0)), 3)
                track_centers.append((bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2))
                prepared.append((bbox, pts))
            track_ids = tracker.update(track_centers, index) if prepared else tracker.update([], index)
            for (bbox, pts), track_id in zip(prepared, track_ids):
                worker = workers_by_track.get(track_id)
                if worker is None:
                    worker = Worker(run_id=run.id, source_track_id=track_id, first_frame=index, last_frame=index, confidence=0.0)
                    db.add(worker); db.flush()
                    workers_by_track[track_id] = worker
                worker.last_frame = index
                confidence = round(sum(p[2] for p in pts.values()) / len(pts), 3)
                angles = {
                    "left_knee": _angle(pts["left_hip"][:2], pts["left_knee"][:2], pts["left_ankle"][:2]),
                    "right_knee": _angle(pts["right_hip"][:2], pts["right_knee"][:2], pts["right_ankle"][:2]),
                    "left_elbow": _angle(pts["left_shoulder"][:2], pts["left_elbow"][:2], pts["left_wrist"][:2]),
                    "right_elbow": _angle(pts["right_shoulder"][:2], pts["right_elbow"][:2], pts["right_wrist"][:2]),
                    "left_shoulder_elevation": _angle(pts["left_hip"][:2], pts["left_shoulder"][:2], pts["left_elbow"][:2]),
                    "right_shoulder_elevation": _angle(pts["right_hip"][:2], pts["right_shoulder"][:2], pts["right_elbow"][:2]),
                    "trunk_flexion": round(abs(90 - math.degrees(math.atan2(abs(pts["right_shoulder"][1] - pts["right_hip"][1]), abs(pts["right_shoulder"][0] - pts["right_hip"][0]) or 1))), 1),
                }
                reba = _reba(angles, confidence)
                pose_2d = {"format": "mediapipe_pose", "coordinate_space": "pixel", "frame_width": width, "frame_height": height, "keypoints": {k: {"x": round(v[0], 2), "y": round(v[1], 2), "confidence": v[2]} for k, v in pts.items()}}
                sources = {
                    "left_knee": ["left_hip", "left_knee", "left_ankle"], "right_knee": ["right_hip", "right_knee", "right_ankle"],
                    "left_elbow": ["left_shoulder", "left_elbow", "left_wrist"], "right_elbow": ["right_shoulder", "right_elbow", "right_wrist"],
                    "left_shoulder_elevation": ["left_hip", "left_shoulder", "left_elbow"], "right_shoulder_elevation": ["right_hip", "right_shoulder", "right_elbow"],
                    "trunk_flexion": ["right_shoulder", "right_hip"],
                }
                db.add(FrameObservation(run_id=run.id, worker_id=worker.id, frame_index=index, timestamp_ms=round(index * 1000 / fps), bbox=bbox, pose_2d=pose_2d, confidence=confidence, angles={k: {"degrees": v, "confidence": confidence, "source_keypoints": sources[k]} for k, v in angles.items()}, reba=reba))
                frame_rows.append({"frame_index": index, "timestamp_ms": round(index * 1000 / fps), "worker_id": worker.id, "track_id": track_id, "score": reba["score"], "confidence": confidence})
                _draw_annotation(frame, bbox, pts, track_id, reba["score"], reba["risk_level"], cv2)
                if reba["score"] >= 8: evidence_candidates.append((index, worker.id, confidence, frame.copy(), reba))
            writer.write(frame); index += 1
            if index == 1 or index % preview_every == 0:
                _write_progress_preview(frame, progress_preview, cv2)
                detected_count = len({item["frame_index"] for item in frame_rows})
                peak_score = max((item["score"] for item in frame_rows), default=0)
                _update_progress(db, run, stage="scoring_reba", current_frame=index, total_frames=total_frames, detected_frames=detected_count, peak_reba=peak_score, commit=True)
    finally:
        pose.close(); capture.release(); writer.release()
    if not frame_rows: raise RuntimeError("no_pose_detected: no person pose was detected in the uploaded video")
    _update_progress(db, run, stage="exporting_video", current_frame=index, total_frames=total_frames or index, detected_frames=len({item["frame_index"] for item in frame_rows}), peak_reba=max(item["score"] for item in frame_rows), commit=True)
    conversion = subprocess.run(["ffmpeg", "-y", "-i", str(annotated_source), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(annotated)], capture_output=True, text=True)
    if conversion.returncode != 0 or not annotated.is_file():
        detail = conversion.stderr.strip().splitlines()[-1] if conversion.stderr.strip() else "ffmpeg did not produce an output file"
        raise RuntimeError(f"annotated_video_transcode_failed: {detail}")
    annotated_source.unlink(missing_ok=True)
    for worker in workers_by_track.values():
        worker_rows = [x for x in frame_rows if x["worker_id"] == worker.id]
        worker.confidence = round(sum(x["confidence"] for x in worker_rows) / len(worker_rows), 3)
    high_by_worker: dict[str, list[dict[str, Any]]] = {}
    for row in frame_rows:
        if row["score"] >= 8:
            high_by_worker.setdefault(row["worker_id"], []).append(row)
    for worker_id, high in high_by_worker.items():
        groups: list[list[dict[str, Any]]] = []
        for row in high:
            if not groups or row["frame_index"] > groups[-1][-1]["frame_index"] + 1:
                groups.append([row])
            else:
                groups[-1].append(row)
        for event_rows in groups:
            event_evidence = [item for item in evidence_candidates if item[1] == worker_id and event_rows[0]["frame_index"] <= item[0] <= event_rows[-1]["frame_index"]]
            event = RiskEvent(run_id=run.id, worker_id=worker_id, start_frame=event_rows[0]["frame_index"], end_frame=event_rows[-1]["frame_index"], start_ms=event_rows[0]["timestamp_ms"], end_ms=event_rows[-1]["timestamp_ms"], peak_score=float(max(x["score"] for x in event_rows)), mean_score=round(sum(x["score"] for x in event_rows) / len(event_rows), 2), body_region="trunk_and_lower_limb", repetition_count=1, confidence=round(sum(x["confidence"] for x in event_rows) / len(event_rows), 3), details={"rule_version": "reba-standard-proxy-0.2", "evidence_count": min(3, len(event_evidence))})
            db.add(event); db.flush()
            for frame_index, _, _, image, _ in event_evidence[:3]:
                path = Path(DATA_ROOT) / "evidence" / run.id; path.mkdir(parents=True, exist_ok=True); target = path / f"frame-{frame_index:06d}.jpg"; cv2.imwrite(str(target), image); content = target.read_bytes()
                db.add(EvidenceFrame(run_id=run.id, event_id=event.id, worker_id=worker_id, frame_index=frame_index, storage_path=str(Path("evidence") / run.id / target.name), sha256=hashlib.sha256(content).hexdigest(), reason="REBA score reached high risk threshold"))
            risk_rows.append({"event_id": event.id, "worker_id": worker_id, "start_frame": event.start_frame, "end_frame": event.end_frame, "start_ms": event.start_ms, "end_ms": event.end_ms, "peak_score": event.peak_score})
    _update_progress(db, run, stage="building_evidence", current_frame=index, total_frames=total_frames or index, detected_frames=len({item["frame_index"] for item in frame_rows}), peak_reba=max(item["score"] for item in frame_rows))
    component = RunComponent(run_id=run.id, name="MediaPipe Pose", version=getattr(mp, "__version__", "unknown"), source_url="https://github.com/google-ai-edge/mediapipe", license="Apache-2.0")
    db.add(component)
    annotated_rel = str(Path("results") / run.id / annotated.name); content = annotated.read_bytes(); run.artifacts.append(ResultArtifact(kind="annotated_video", storage_path=annotated_rel, sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content), mime_type="video/mp4"))
    detected_frame_count = len({x["frame_index"] for x in frame_rows})
    run.model_summary = {"name": "MediaPipe Pose", "version": getattr(mp, "__version__", "unknown"), "detector": detector_mode(), "frames": index, "detected_frames": detected_frame_count, "detected_observations": len(frame_rows), "workers": len(workers_by_track), "fps": fps, "mean_confidence": round(sum(x["confidence"] for x in frame_rows) / len(frame_rows), 3), "peak_reba": max(x["score"] for x in frame_rows), "risk_events": len(risk_rows)}
    run.ruleset_version = "reba-standard-proxy-0.2"
    return {"schema_version": "1.0", "run_id": run.id, "generated_at": utcnow().isoformat(), "model": run.model_summary, "ruleset_version": run.ruleset_version, "summary": {"frames": index, "detected_frames": detected_frame_count, "detected_observations": len(frame_rows), "workers": len(workers_by_track), "risk_events": len(risk_rows), "peak_reba": max(x["score"] for x in frame_rows)}, "frames": frame_rows, "risk_events": risk_rows}
