from __future__ import annotations

from sqlalchemy import select

from .db import AnalysisRun, EvidenceFrame, FrameObservation, RiskEvent, Worker


def answer_question(db, run_id: str, question: str) -> dict:
    """Deterministic, evidence-grounded assistant for the MVP.

    It deliberately reads only persisted facts; no model is allowed to invent a result.
    """
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError("run does not exist")
    events = db.scalars(select(RiskEvent).where(RiskEvent.run_id == run_id).order_by(RiskEvent.start_ms)).all()
    workers = db.scalars(select(Worker).where(Worker.run_id == run_id).order_by(Worker.source_track_id)).all()
    tools = [{"tool": "get_run_summary", "arguments": {"run_id": run_id}}, {"tool": "find_risk_events", "arguments": {"run_id": run_id}}]
    citations = [{"type": "run", "run_id": run_id}]
    q = question.lower()
    if any(token in q for token in ("证据", "哪一帧", "frame", "截图")):
        tools.append({"tool": "inspect_risk_event", "arguments": {"run_id": run_id}})
    if any(token in q for token in ("角度", "关节", "joint")):
        tools.append({"tool": "get_joint_angles", "arguments": {"run_id": run_id}})
    peak = run.model_summary.get("peak_reba")
    confidence = run.model_summary.get("mean_confidence")
    observations = db.scalars(select(FrameObservation).where(FrameObservation.run_id == run_id).order_by(FrameObservation.frame_index)).all()
    if events:
        highest = max(events, key=lambda event: (event.peak_score, event.mean_score, -event.start_ms))
        answer = f"检测到 {len(events)} 个高风险事件。最高事件 REBA {highest.peak_score:g}，时间为 {highest.start_ms}–{highest.end_ms} ms，身体部位为 {highest.body_region}。"
        tools[1]["arguments"]["event_id"] = highest.id
        citations.append({"type": "risk_event", "event_id": highest.id, "worker_id": highest.worker_id, "start_frame": highest.start_frame, "end_frame": highest.end_frame})
        evidence = db.scalars(select(EvidenceFrame).where(EvidenceFrame.event_id == highest.id).order_by(EvidenceFrame.frame_index)).all()
        citations.extend({"type": "evidence_frame", "evidence_id": frame.id, "event_id": highest.id, "frame_index": frame.frame_index, "storage_path": frame.storage_path} for frame in evidence)
    else:
        answer = f"本次运行没有达到阈值的高风险事件。逐帧最高 REBA 为 {peak if peak is not None else '未知'}。"
        if "证据" in q or "截图" in q or "frame" in q:
            answer += "由于没有达到高风险阈值，本次运行没有可关联的高风险证据帧。"
    if any(token in q for token in ("角度", "关节", "joint")) and observations:
        representative = max(observations, key=lambda item: (item.reba.get("score", 0), -item.frame_index))
        angle_text = "、".join(
            f"{name} {value.get('degrees') if isinstance(value, dict) else value}°"
            for name, value in representative.angles.items()
            if isinstance(value, dict) and value.get("degrees") is not None
        )
        answer += f" 代表帧为 {representative.frame_index}（Worker {representative.worker_id}），记录角度：{angle_text or '无可用角度'}。"
        citations.append({"type": "frame_observation", "observation_run_id": run_id, "worker_id": representative.worker_id, "frame_index": representative.frame_index, "angles": representative.angles, "reba": representative.reba})
    if confidence is not None:
        answer += f" 平均姿态置信度为 {confidence:.0%}。"
    answer += " 结论仅来自已保存的姿态、角度和规则结果，使用前请复核原始视频。"
    citations.extend({"type": "worker", "worker_id": worker.id, "track_id": worker.source_track_id} for worker in workers)
    return {"answer": answer, "question": question, "run_id": run_id, "tool_calls": tools, "citations": citations, "limitations": ["MVP 助手不调用外部大模型，不替代人工或职业卫生专业判断。"]}
