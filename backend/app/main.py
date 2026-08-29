from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import AnalysisTask, init_db, new_task, session

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ergoagent.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="ErgoAgent API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class TaskCreate(BaseModel):
    source_name: str = Field(min_length=1, max_length=255)


class TaskResponse(BaseModel):
    id: str
    status: str
    source_name: str
    error_message: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, task: AnalysisTask) -> "TaskResponse":
        return cls(
            id=task.id,
            status=task.status,
            source_name=task.source_name,
            error_message=task.error_message,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ergoagent-api", "version": app.version}


@app.post("/api/tasks", response_model=TaskResponse, status_code=201)
def create_task(payload: TaskCreate) -> TaskResponse:
    with session() as db:
        task = new_task(payload.source_name)
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info('{"event":"task_created","task_id":"%s"}', task.id)
        return TaskResponse.from_model(task)


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str) -> TaskResponse:
    with session() as db:
        task = db.get(AnalysisTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return TaskResponse.from_model(task)


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    run()
