from __future__ import annotations
import base64
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from .db import AnalysisRun, AnalysisTask, EvidenceFrame, FrameObservation, RiskEvent, VideoAsset, Worker, init_db, new_task, session, utcnow
from .storage import save_upload, resolve_safe, media_metadata, remove_relative
from .services import create_retry_run

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ergoagent.api")

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield

app = FastAPI(title="ErgoAgent API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

class TaskCreate(BaseModel):
    video_asset_id: str | None = None
    profile: str | None = Field(default=None, max_length=100)
    source_name: str | None = Field(default=None, min_length=1, max_length=255)

class AssistantQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

def error(code: str, message: str, status: int = 400):
    raise HTTPException(status_code=status, detail={"code": code, "message": message, "details": {}})

def task_json(task: AnalysisTask) -> dict:
    latest = max(task.runs, key=lambda r: r.attempt, default=None)
    return {"id": task.id, "task_id": task.id, "video_asset_id": task.video_asset_id, "status": task.status, "source_name": task.source_name, "requested_at": task.requested_at.isoformat(), "created_at": task.created_at.isoformat(), "updated_at": task.updated_at.isoformat(), "started_at": task.started_at.isoformat() if task.started_at else None, "finished_at": task.finished_at.isoformat() if task.finished_at else None, "error_code": task.error_code, "error_message": task.error_message, "run_id": latest.id if latest else None, "progress_stage": task.progress_stage, "progress_current_frame": task.progress_current_frame, "progress_total_frames": task.progress_total_frames, "progress_detected_frames": task.progress_detected_frames, "progress_peak_reba": task.progress_peak_reba}

def video_asset_json(asset: VideoAsset, reused: bool = False) -> dict:
    return {"video_asset_id": asset.id, "original_name": asset.original_name, "storage_path": asset.storage_path, "sha256": asset.sha256, "size_bytes": asset.size_bytes, "mime_type": asset.mime_type, "duration_ms": asset.duration_ms, "width": asset.width, "height": asset.height, "fps": asset.fps, "created_at": asset.created_at.isoformat(), "reused": reused}

@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    from fastapi.responses import JSONResponse
    detail = exc.detail if isinstance(exc.detail, dict) and "code" in exc.detail else {"code": "http_error", "message": str(exc.detail), "details": {}}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})

@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"error": {"code": "invalid_parameters", "message": "request parameters are invalid", "details": {"errors": exc.errors()}}})

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ergoagent-api", "version": app.version}

@app.post("/api/videos", status_code=201)
async def upload_video(file: UploadFile = File(...)):
    path, digest, size = await save_upload(file)
    with session() as db:
        existing = db.scalar(select(VideoAsset).where(VideoAsset.sha256 == digest))
        if existing:
            remove_relative(path)
            return video_asset_json(existing, reused=True)
        metadata = media_metadata(path)
        from .config import MAX_VIDEO_DURATION_SECONDS
        if metadata.get("duration_ms") and metadata["duration_ms"] > MAX_VIDEO_DURATION_SECONDS * 1000:
            resolve_safe(path).unlink(missing_ok=True)
            error("video_too_long", "video exceeds duration limit", 413)
        asset = VideoAsset(original_name=file.filename or "video", storage_path=path, sha256=digest, size_bytes=size, mime_type=file.content_type or "application/octet-stream", **metadata)
        db.add(asset); db.commit(); db.refresh(asset)
        return video_asset_json(asset)

@app.post("/api/analysis-tasks", status_code=201)
def create_analysis_task(payload: TaskCreate):
    with session() as db:
        video = db.get(VideoAsset, payload.video_asset_id) if payload.video_asset_id else None
        if not payload.video_asset_id: error("video_required", "video_asset_id is required", 422)
        if video is None: error("video_not_found", "video does not exist", 404)
        active = db.scalar(select(func.count(AnalysisTask.id)).where(AnalysisTask.video_asset_id == video.id, AnalysisTask.status.in_(["queued", "running"])))
        if active: error("video_busy", "video already has an active analysis task", 409)
        source = payload.source_name or (video.original_name if video else "unknown")
        task = new_task(source, payload.video_asset_id, payload.profile)
        db.add(task); db.commit(); db.refresh(task)
        return task_json(task)

@app.post("/api/tasks", status_code=201)
def create_legacy_task(payload: TaskCreate):
    if not payload.source_name:
        error("source_name_required", "source_name is required for the legacy endpoint", 422)
    with session() as db:
        task = new_task(payload.source_name, profile=payload.profile)
        db.add(task)
        db.commit()
        db.refresh(task)
        return task_json(task)

@app.get("/api/analysis-tasks/{task_id}")
@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    with session() as db:
        task = db.get(AnalysisTask, task_id)
        if task is None: error("not_found", "task does not exist", 404)
        return task_json(task)

@app.get("/api/analysis-tasks/{task_id}/progress-preview")
def task_progress_preview(task_id: str):
    from fastapi.responses import FileResponse, Response
    with session() as db:
        task = db.get(AnalysisTask, task_id)
        if task is None: error("not_found", "task does not exist", 404)
        latest = max(task.runs, key=lambda item: item.attempt, default=None)
        if latest is None:
            return Response(status_code=204)
        path = resolve_safe(f"results/{latest.id}/progress.jpg")
        if not path.is_file():
            return Response(status_code=204)
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

@app.post("/api/analysis-tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    with session() as db:
        task = db.get(AnalysisTask, task_id)
        if task is None: error("not_found", "task does not exist", 404)
        if task.status == "queued":
            task.status = "cancelled"
            task.finished_at = task.updated_at = utcnow()
        elif task.status == "running":
            task.cancel_requested_at = utcnow()
        else:
            error("invalid_state", "task is already complete", 409)
        db.commit()
        return task_json(task)

@app.post("/api/analysis-tasks/{task_id}/retry", status_code=201)
def retry_task(task_id: str):
    with session() as db:
        task = db.get(AnalysisTask, task_id)
        if task is None: error("not_found", "task does not exist", 404)
        try:
            run = create_retry_run(db, task)
        except ValueError as exc:
            error("invalid_state", str(exc), 409)
        db.commit(); db.refresh(task)
        return {"task_id": task.id, "status": task.status, "attempt": run.attempt}

@app.get("/api/videos/{video_id}")
def get_video(video_id: str):
    with session() as db:
        asset = db.get(VideoAsset, video_id)
        if asset is None: error("not_found", "video does not exist", 404)
        count = db.scalar(select(func.count(AnalysisRun.id)).where(AnalysisRun.input_video_id == asset.id, AnalysisRun.status == "succeeded")) or 0
        return {"video_asset_id": asset.id, "original_name": asset.original_name, "storage_path": asset.storage_path, "sha256": asset.sha256, "size_bytes": asset.size_bytes, "mime_type": asset.mime_type, "duration_ms": asset.duration_ms, "width": asset.width, "height": asset.height, "fps": asset.fps, "result_count": count, "created_at": asset.created_at.isoformat()}

@app.get("/api/analysis-runs/{run_id}")
def get_run(run_id: str):
    with session() as db:
        run = db.get(AnalysisRun, run_id)
        if run is None: error("not_found", "run does not exist", 404)
        summary = dict(run.model_summary)
        if run.status == "succeeded" and "peak_reba" not in summary:
            scores = [row.reba.get("score") for row in db.scalars(select(FrameObservation).where(FrameObservation.run_id == run.id)).all()]
            summary["peak_reba"] = max((score for score in scores if isinstance(score, (int, float))), default=None)
        return {"id": run.id, "task_id": run.task_id, "attempt": run.attempt, "status": run.status, "input_video_id": run.input_video_id, "schema_version": run.schema_version, "model_summary": summary, "ruleset_version": run.ruleset_version, "generated_at": run.generated_at.isoformat(), "started_at": run.started_at.isoformat() if run.started_at else None, "finished_at": run.finished_at.isoformat() if run.finished_at else None, "error_code": run.error_code, "error_message": run.error_message, "components": [{"name": c.name, "version": c.version, "source_url": c.source_url, "license": c.license} for c in run.components], "artifacts": [{"kind": a.kind, "storage_path": a.storage_path, "sha256": a.sha256, "size_bytes": a.size_bytes, "mime_type": a.mime_type} for a in run.artifacts]}

def cursor_page(items, limit: int):
    page = items[:limit]
    return {"items": page, "next_cursor": None if len(items) <= limit else base64.urlsafe_b64encode(str(page[-1]["id"]).encode()).decode()}

def decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        return base64.urlsafe_b64decode(cursor.encode()).decode()
    except Exception:
        error("invalid_cursor", "cursor is invalid", 422)

@app.get("/api/analysis-runs/{run_id}/workers")
def list_workers(run_id: str, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
    with session() as db:
        if db.get(AnalysisRun, run_id) is None: error("not_found", "run does not exist", 404)
        stmt = select(Worker).where(Worker.run_id == run_id).order_by(Worker.id)
        if (after := decode_cursor(cursor)): stmt = stmt.where(Worker.id > after)
        rows = db.scalars(stmt.limit(limit + 1)).all()
        return cursor_page([{"id": w.id, "source_track_id": w.source_track_id, "first_frame": w.first_frame, "last_frame": w.last_frame, "confidence": w.confidence} for w in rows], limit)

@app.get("/api/analysis-runs/{run_id}/risk-events")
def list_events(run_id: str, worker_id: str | None = None, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
    with session() as db:
        if db.get(AnalysisRun, run_id) is None: error("not_found", "run does not exist", 404)
        stmt = select(RiskEvent).where(RiskEvent.run_id == run_id).order_by(RiskEvent.id)
        if worker_id: stmt = stmt.where(RiskEvent.worker_id == worker_id)
        if (after := decode_cursor(cursor)): stmt = stmt.where(RiskEvent.id > after)
        rows = db.scalars(stmt.limit(limit + 1)).all()
        return cursor_page([{"id": e.id, "run_id": e.run_id, "worker_id": e.worker_id, "start_frame": e.start_frame, "end_frame": e.end_frame, "start_ms": e.start_ms, "end_ms": e.end_ms, "peak_score": e.peak_score, "mean_score": e.mean_score, "body_region": e.body_region, "repetition_count": e.repetition_count, "confidence": e.confidence, "details": e.details} for e in rows], limit)

@app.get("/api/risk-events/{event_id}")
def get_event(event_id: str):
    with session() as db:
        event_row = db.get(RiskEvent, event_id)
        if event_row is None: error("not_found", "risk event does not exist", 404)
        evidence = db.scalars(select(EvidenceFrame).where(EvidenceFrame.event_id == event_id).order_by(EvidenceFrame.frame_index)).all()
        return {"id": event_row.id, "run_id": event_row.run_id, "worker_id": event_row.worker_id, "start_frame": event_row.start_frame, "end_frame": event_row.end_frame, "start_ms": event_row.start_ms, "end_ms": event_row.end_ms, "peak_score": event_row.peak_score, "mean_score": event_row.mean_score, "body_region": event_row.body_region, "repetition_count": event_row.repetition_count, "confidence": event_row.confidence, "details": event_row.details, "evidence_frames": [{"id": x.id, "frame_index": x.frame_index, "storage_path": x.storage_path, "sha256": x.sha256, "reason": x.reason} for x in evidence]}

@app.get("/api/evidence-frames/{evidence_id}/content")
def evidence_content(evidence_id: str):
    from fastapi.responses import FileResponse
    with session() as db:
        item = db.get(EvidenceFrame, evidence_id)
        if item is None: error("not_found", "evidence frame does not exist", 404)
        try: path = resolve_safe(item.storage_path)
        except ValueError: error("invalid_storage_path", "invalid storage path", 500)
        if not path.is_file(): error("file_gone", "evidence file has been removed", 410)
        return FileResponse(path, media_type="image/jpeg")

@app.get("/api/analysis-runs/{run_id}/artifacts/{kind}/content")
def artifact_content(run_id: str, kind: str):
    from fastapi.responses import FileResponse
    with session() as db:
        run = db.get(AnalysisRun, run_id)
        if run is None: error("not_found", "run does not exist", 404)
        artifact = next((item for item in run.artifacts if item.kind == kind), None)
        if artifact is None: error("not_found", "result artifact does not exist", 404)
        try: path = resolve_safe(artifact.storage_path)
        except ValueError: error("invalid_storage_path", "invalid storage path", 500)
        if not path.is_file(): error("file_gone", "result file has been removed", 410)
        return FileResponse(path, media_type=artifact.mime_type)

@app.post("/api/analysis-runs/{run_id}/assistant")
def run_assistant(run_id: str, payload: AssistantQuestion):
    with session() as db:
        try:
            from .agent import answer_question
            return answer_question(db, run_id, payload.question)
        except ValueError as exc:
            error("not_found", str(exc), 404)

@app.get("/api/analysis-runs/{run_id}/baseline")
def baseline_status(run_id: str):
    with session() as db:
        run = db.get(AnalysisRun, run_id)
        if run is None: error("not_found", "run does not exist", 404)
        from .baselines import load_manifest
        manifest = load_manifest()
        reference = dict(manifest.get("reference", {}))
        reference.update({"version": run.model_summary.get("version", reference.get("version", "unknown")), "status": "executed"})
        return {
            "run_id": run_id,
            "manifest_version": manifest.get("manifest_version", "unknown"),
            "reference": reference,
            "candidates": manifest.get("candidates", []),
            "metrics": {"peak_reba": run.model_summary.get("peak_reba"), "detected_frames": run.model_summary.get("detected_frames"), "detected_observations": run.model_summary.get("detected_observations"), "frames": run.model_summary.get("frames"), "mean_confidence": run.model_summary.get("mean_confidence")},
            "reproducibility": {"input_video_id": run.input_video_id, "ruleset_version": run.ruleset_version, "run_id": run.id, "comparison_schema_version": "0.1", "metrics_are_comparable": False},
        }

def run() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)

if __name__ == "__main__":
    run()
