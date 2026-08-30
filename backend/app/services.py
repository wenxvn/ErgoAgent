from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from .config import DATA_ROOT
from .db import AnalysisRun, AnalysisTask, ResultArtifact, utcnow

TASK_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


def transition_task(task: AnalysisTask, status: str) -> None:
    if status not in TASK_TRANSITIONS.get(task.status, set()):
        raise ValueError(f"invalid task transition: {task.status} -> {status}")
    task.status = status
    now = utcnow()
    task.updated_at = now
    if status == "running":
        task.started_at = now
    if status in {"succeeded", "failed", "cancelled"}:
        task.finished_at = now
        task.lease_owner = None
        task.lease_expires_at = None


def create_retry_run(db, task: AnalysisTask) -> AnalysisRun:
    if task.status != "failed":
        raise ValueError("only failed tasks can be retried")
    attempt = db.scalar(select(AnalysisRun.attempt).where(AnalysisRun.task_id == task.id).order_by(AnalysisRun.attempt.desc()).limit(1)) or 0
    now = utcnow()
    task.status = "running"
    task.started_at = now
    task.error_code = None
    task.error_message = None
    task.finished_at = None
    task.updated_at = now
    run = AnalysisRun(task_id=task.id, attempt=attempt + 1, status="running", started_at=now, input_video_id=task.video_asset_id)
    db.add(run)
    return run


def write_result_json(db, run: AnalysisRun, payload: dict[str, Any]) -> ResultArtifact:
    if run.status != "running":
        raise ValueError("results can only be written to a running run")
    folder = Path(DATA_ROOT) / "results" / run.id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "result.json"
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    with temporary.open("wb") as handle:
        handle.write(content)
        handle.flush()
    temporary.replace(target)
    digest = hashlib.sha256(content).hexdigest()
    artifact = ResultArtifact(run_id=run.id, kind="result_json", storage_path=str(Path("results") / run.id / "result.json"), sha256=digest, size_bytes=len(content), mime_type="application/json")
    db.add(artifact)
    return artifact


def complete_run(db, run: AnalysisRun, status: str, error_code: str | None = None, error_message: str | None = None) -> None:
    if status not in {"succeeded", "failed", "cancelled"} or run.status != "running":
        raise ValueError("invalid run completion")
    if status == "succeeded" and not db.scalar(select(ResultArtifact.id).where(ResultArtifact.run_id == run.id, ResultArtifact.kind == "result_json")):
        raise ValueError("successful run requires a result_json artifact")
    run.status = status
    run.finished_at = utcnow()
    run.error_code = error_code
    run.error_message = error_message
    task = db.get(AnalysisTask, run.task_id)
    if task and task.status == "running":
        transition_task(task, status)


def fail_expired_run(db, run: AnalysisRun, message: str = "worker lease expired") -> None:
    """Close an interrupted run without overwriting its historical attempt."""
    complete_run(db, run, "failed", "worker_lease_expired", message)
