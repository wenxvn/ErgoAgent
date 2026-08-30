from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path(__file__).resolve().parents[2] / "docs" / "research" / "baseline-manifest.json"


def load_manifest() -> dict[str, Any]:
    """Load the checked-in baseline registry without network access."""
    if not MANIFEST_PATH.is_file():
        return {"manifest_version": "unknown", "reference": {}, "candidates": []}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
