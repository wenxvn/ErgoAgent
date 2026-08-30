from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.getenv("ERGOAGENT_DATA_ROOT", PROJECT_ROOT / "data"))
DATABASE_URL = os.getenv(
    "ERGOAGENT_DATABASE_URL",
    f"sqlite:///{(DATA_ROOT / 'ergoagent.db').as_posix()}",
)
MAX_VIDEO_DURATION_SECONDS = int(os.getenv("ERGOAGENT_MAX_VIDEO_DURATION_SECONDS", "1800"))
RETENTION_DAYS = int(os.getenv("ERGOAGENT_RETENTION_DAYS", "30"))


def ensure_data_directories() -> None:
    for name in ("uploads", "results", "evidence"):
        (DATA_ROOT / name).mkdir(parents=True, exist_ok=True)
