from __future__ import annotations

import logging
import time

from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, update

from .db import AnalysisRun, AnalysisTask, init_db, session, utcnow
from .services import complete_run

logger = logging.getLogger("ergoagent.worker")


def claim_one_task(worker_id: str | None = None) -> bool:
    worker_id = worker_id or str(uuid4())
    with session() as db:
        task = db.scalar(select(AnalysisTask).where(AnalysisTask.status == "queued").order_by(AnalysisTask.created_at).limit(1))
        if task is None:
            return False
        now = utcnow()
        claimed = db.execute(update(AnalysisTask).where(AnalysisTask.id == task.id, AnalysisTask.status == "queued").values(status="running", started_at=now, lease_owner=worker_id, lease_expires_at=now + timedelta(minutes=5), updated_at=now))
        if claimed.rowcount != 1:
            return False
        attempt = (db.scalar(select(AnalysisRun.attempt).where(AnalysisRun.task_id == task.id).order_by(AnalysisRun.attempt.desc()).limit(1)) or 0) + 1
        run = AnalysisRun(task_id=task.id, attempt=attempt, status="running", started_at=now, input_video_id=task.video_asset_id)
        db.add(run)
        db.commit()
        logger.info('{"event":"task_started","task_id":"%s"}', task.id)
        return True


def finish_run(run_id: str, worker_id: str, payload: dict) -> None:
    with session() as db:
        run = db.get(AnalysisRun, run_id)
        if run is None or run.task.lease_owner != worker_id:
            raise ValueError("worker does not own this run")
        from .services import write_result_json
        write_result_json(db, run, payload)
        complete_run(db, run, "succeeded")
        db.commit()


def fail_run(run_id: str, worker_id: str, code: str, message: str) -> None:
    with session() as db:
        run = db.get(AnalysisRun, run_id)
        if run is None or run.task.lease_owner != worker_id:
            raise ValueError("worker does not own this run")
        complete_run(db, run, "failed", code, message)
        db.commit()


def run() -> None:
    init_db()
    logger.info("ErgoAgent Worker 已启动，等待分析任务")
    while True:
        claim_one_task()
        time.sleep(1)


if __name__ == "__main__":
    run()
