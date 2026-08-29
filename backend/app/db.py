from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import DATABASE_URL, DATA_ROOT, ensure_data_directories


class Base(DeclarativeBase):
    pass


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    ensure_data_directories()
    Path(DATA_ROOT).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def new_task(source_name: str) -> AnalysisTask:
    now = datetime.now(timezone.utc)
    return AnalysisTask(
        id=str(uuid4()),
        status="queued",
        source_name=source_name,
        created_at=now,
        updated_at=now,
    )


def session() -> Session:
    return SessionLocal()
