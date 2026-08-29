from __future__ import annotations

import logging
import time

from sqlalchemy import select

from .db import AnalysisTask, init_db, session

logger = logging.getLogger("ergoagent.worker")


def claim_one_task() -> bool:
    with session() as db:
        task = db.scalar(
            select(AnalysisTask)
            .where(AnalysisTask.status == "queued")
            .order_by(AnalysisTask.created_at)
            .limit(1)
        )
        if task is None:
            return False
        task.status = "running"
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
