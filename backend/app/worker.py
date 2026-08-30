from __future__ import annotations

import logging
import time

from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select

from .db import AnalysisRun, AnalysisTask, init_db, session, utcnow

logger = logging.getLogger("ergoagent.worker")


def claim_one_task(worker_id: str | None = None) -> bool:
    worker_id = worker_id or str(uuid4())
    with session() as db:
        task = db.scalar(
            select(AnalysisTask)
            .where(AnalysisTask.status == "queued")
            .order_by(AnalysisTask.created_at)
            .limit(1)
        )
        if task is None:
            return False
        now = utcnow()
        task.status = "running"
        task.started_at = now
        task.lease_owner = worker_id
        task.lease_expires_at = now + timedelta(minutes=5)
        attempt = (db.scalar(select(AnalysisRun.attempt).where(AnalysisRun.task_id == task.id).order_by(AnalysisRun.attempt.desc()).limit(1)) or 0) + 1
        run = AnalysisRun(task_id=task.id, attempt=attempt, status="running", started_at=now, input_video_id=task.video_asset_id)
        db.add(run)
        db.commit()
        logger.info('{"event":"task_started","task_id":"%s"}', task.id)
        return True


def run() -> None:
    init_db()
    logger.info("ErgoAgent Worker 已启动，等待分析任务")
    while True:
        claim_one_task()
        time.sleep(1)


if __name__ == "__main__":
    run()
