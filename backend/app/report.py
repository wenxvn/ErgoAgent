from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .config import DATA_ROOT
from .db import AnalysisRun, ResultArtifact, utcnow


def write_report(db, run: AnalysisRun, payload: dict[str, Any]) -> ResultArtifact:
    """Write a small self-contained audit report from persisted analysis facts."""
    summary = payload.get("summary", {})
    events = payload.get("risk_events", [])
    report = {
        "report_version": "0.1",
        "generated_at": utcnow().isoformat(),
        "run_id": run.id,
        "task_id": run.task_id,
        "source_name": run.task.source_name if run.task else None,
        "model": run.model_summary,
        "ruleset_version": run.ruleset_version,
        "summary": summary,
        "risk_events": events,
        "limitations": [
            "默认使用 MediaPipe Pose；设置 ERGOAGENT_PERSON_DETECTOR=hog 可启用 OpenCV HOG 多人实验模式，候选框碎片化、遮挡和 ID 交换仍需人工复核。",
            "reba-standard-proxy-0.2 使用 REBA 表格，但视频未提供负荷、耦合、扭转和活动频率时显式采用中性值，不等同于正式职业工效诊断。",
            "风险事件必须结合原始视频和证据帧人工复核。",
        ],
    }
    folder = Path(DATA_ROOT) / "results" / run.id
    folder.mkdir(parents=True, exist_ok=True)
    json_target = folder / "report.json"
    json_target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = "".join(
        f"<tr><td>{html.escape(str(event.get('event_id', '')))}</td><td>{event.get('start_ms', 0)}–{event.get('end_ms', 0)} ms</td><td>{event.get('peak_score', '')}</td></tr>"
        for event in events
    ) or "<tr><td colspan='3'>未发现高风险事件</td></tr>"
    html_target = folder / "report.html"
    html_target.write_text(
        "<!doctype html><meta charset='utf-8'><title>ErgoAgent 分析报告</title>"
        f"<h1>ErgoAgent 分析报告</h1><p>运行 {html.escape(run.id)}</p><p>输入视频：{html.escape(run.task.source_name if run.task and run.task.source_name else 'unknown')}</p>"
        f"<p>模型：{html.escape(str(run.model_summary.get('name', 'unknown')))} {html.escape(str(run.model_summary.get('version', '')))}；规则：{html.escape(run.ruleset_version)}</p>"
        f"<p>总帧数：{summary.get('frames', 0)}；检测帧：{summary.get('detected_frames', 0)}；峰值 REBA：{summary.get('peak_reba', '—')}</p>"
        f"<table border='1' cellpadding='6'><thead><tr><th>事件</th><th>时间</th><th>峰值</th></tr></thead><tbody>{rows}</tbody></table>"
        "<h2>限制</h2><ul><li>默认使用 MediaPipe Pose；HOG 多人模式为实验能力，候选框碎片化、遮挡和 ID 交换仍需复核。</li><li>REBA 表格中视频未提供的负荷、耦合、扭转和活动频率采用显式中性值，不等同于正式职业工效诊断。</li><li>风险事件必须结合原始视频和证据帧人工复核。</li></ul>",
        encoding="utf-8",
    )
    import hashlib
    html_content = html_target.read_bytes()
    json_content = json_target.read_bytes()
    html_artifact = ResultArtifact(
        run_id=run.id,
        kind="report",
        storage_path=str(Path("results") / run.id / "report.html"),
        sha256=hashlib.sha256(html_content).hexdigest(),
        size_bytes=len(html_content),
        mime_type="text/html",
    )
    json_artifact = ResultArtifact(
        run_id=run.id,
        kind="report_json",
        storage_path=str(Path("results") / run.id / "report.json"),
        sha256=hashlib.sha256(json_content).hexdigest(),
        size_bytes=len(json_content),
        mime_type="application/json",
    )
    db.add_all([html_artifact, json_artifact])
    return html_artifact
