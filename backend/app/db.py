from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from .config import DATABASE_URL, DATA_ROOT, ensure_data_directories


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoAsset(Base):
    __tablename__ = "video_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    video_asset_id: Mapped[str | None] = mapped_column(ForeignKey("video_assets.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    profile: Mapped[str | None] = mapped_column(String(100))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="task")
    __table_args__ = (CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="ck_task_status"),)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("analysis_tasks.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    input_video_id: Mapped[str | None] = mapped_column(ForeignKey("video_assets.id"))
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    model_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ruleset_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    task: Mapped[AnalysisTask] = relationship(back_populates="runs")
    components: Mapped[list["RunComponent"]] = relationship(back_populates="run")
    workers: Mapped[list["Worker"]] = relationship(back_populates="run")
    artifacts: Mapped[list["ResultArtifact"]] = relationship(back_populates="run")
    __table_args__ = (UniqueConstraint("task_id", "attempt", name="uq_run_attempt"), CheckConstraint("status IN ('running','succeeded','failed','cancelled')", name="ck_run_status"))


class RunComponent(Base):
    __tablename__ = "run_components"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    license: Mapped[str] = mapped_column(String(128), nullable=False)
    weight_uri: Mapped[str | None] = mapped_column(String(1024))
    weight_sha256: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("run_id", "name", "version", name="uq_component"),)
    run: Mapped[AnalysisRun] = relationship(back_populates="components")


class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    source_track_id: Mapped[str] = mapped_column(String(128), nullable=False)
    first_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    last_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    run: Mapped[AnalysisRun] = relationship(back_populates="workers")
    __table_args__ = (UniqueConstraint("run_id", "source_track_id", name="uq_worker_track"), CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_worker_confidence"))


class FrameObservation(Base):
    __tablename__ = "frame_observations"
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), primary_key=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), primary_key=True)
    frame_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox: Mapped[dict] = mapped_column(JSON, nullable=False)
    pose_2d: Mapped[dict] = mapped_column(JSON, nullable=False)
    pose_3d: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    angles: Mapped[dict] = mapped_column(JSON, nullable=False)
    reba: Mapped[dict] = mapped_column(JSON, nullable=False)
    __table_args__ = (Index("ix_observation_run_time", "run_id", "timestamp_ms"), CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_observation_confidence"))


class RiskEvent(Base):
    __tablename__ = "risk_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), nullable=False)
    start_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    end_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    peak_score: Mapped[float] = mapped_column(Float, nullable=False)
    mean_score: Mapped[float] = mapped_column(Float, nullable=False)
    body_region: Mapped[str] = mapped_column(String(64), nullable=False)
    repetition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (Index("ix_risk_run_worker_start", "run_id", "worker_id", "start_ms"), CheckConstraint("end_frame >= start_frame", name="ck_event_frames"), CheckConstraint("end_ms >= start_ms", name="ck_event_time"), CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_event_confidence"))


class EvidenceFrame(Base):
    __tablename__ = "evidence_frames"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    event_id: Mapped[str] = mapped_column(ForeignKey("risk_events.id"), nullable=False)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), nullable=False)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("event_id", "frame_index", name="uq_evidence_frame"),)


class ResultArtifact(Base):
    __tablename__ = "result_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    run: Mapped[AnalysisRun] = relationship(back_populates="artifacts")
    __table_args__ = (UniqueConstraint("run_id", "kind", name="uq_result_kind"),)


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    ensure_data_directories()
    Path(DATA_ROOT).mkdir(parents=True, exist_ok=True)
    # The scaffold database had only source_name. It is a disposable development artifact.
    if "analysis_tasks" in inspect(engine).get_table_names() and "video_asset_id" not in {c["name"] for c in inspect(engine).get_columns("analysis_tasks")}:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def new_task(source_name: str, video_asset_id: str | None = None, profile: str | None = None) -> AnalysisTask:
    now = utcnow()
    return AnalysisTask(id=str(uuid4()), status="queued", source_name=source_name, video_asset_id=video_asset_id, profile=profile, requested_at=now, created_at=now, updated_at=now)


def session() -> Session:
    return SessionLocal()
