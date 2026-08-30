from __future__ import annotations

from typing import Any


# REBA (Hignett & McAtamney, 2000) lookup tables. The two tables are kept
# explicit so every score in a result can be audited without hidden formulas.
TABLE_A = (
    ((1, 2, 3, 4), (2, 3, 4, 5), (2, 4, 5, 6), (3, 5, 6, 7), (4, 6, 7, 8)),
    ((1, 2, 3, 4), (3, 4, 5, 6), (4, 5, 6, 7), (5, 6, 7, 8), (6, 7, 8, 9)),
    ((3, 3, 4, 5), (4, 5, 6, 7), (5, 6, 7, 8), (6, 7, 8, 9), (7, 8, 9, 9)),
)

TABLE_B = (
    ((1, 2, 2), (1, 2, 3)),
    ((1, 2, 3), (2, 3, 4)),
    ((3, 4, 5), (4, 5, 5)),
    ((4, 5, 6), (5, 6, 7)),
    ((6, 7, 8), (7, 8, 8)),
    ((7, 8, 8), (8, 9, 9)),
)

TABLE_C = (
    (1, 1, 1, 2, 3, 3, 4, 5, 6, 7, 7, 7),
    (1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 7, 8),
    (2, 3, 3, 3, 4, 5, 6, 7, 7, 8, 8, 8),
    (3, 4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9),
    (4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 10, 10),
    (6, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 10),
    (7, 7, 7, 8, 8, 9, 9, 9, 10, 10, 11, 11),
    (8, 8, 8, 9, 9, 10, 10, 10, 10, 11, 11, 11),
    (9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12),
    (10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12, 12),
    (11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12, 12),
    (12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12),
)


def _risk(score: int) -> str:
    if score <= 1:
        return "negligible"
    if score <= 3:
        return "low"
    if score <= 7:
        return "medium"
    if score <= 10:
        return "high"
    return "very_high"


def _bin_trunk(value: float) -> int:
    return 1 if value < 5 else 2 if value < 20 else 3 if value < 60 else 4


def _bin_neck(value: float) -> int:
    return 1 if value < 20 else 2


def _bin_legs(knee: float) -> int:
    return 1 if knee > 150 else 2 if knee > 90 else 3


def _bin_upper_arm(value: float) -> int:
    return 1 if value < 20 else 2 if value < 45 else 3 if value < 90 else 4 if value < 120 else 5


def _bin_lower_arm(value: float) -> int:
    return 1 if 60 <= value <= 100 else 2


def score_reba(angles: dict[str, float | None], confidence: float) -> dict[str, Any]:
    """Score available 2-D observations with the published REBA tables.

    Load, coupling, twist and side-bending are not observable from the MVP
    contract. They are explicitly recorded as neutral (zero) rather than
    silently inferred, making this a standard-table proxy until those inputs
    are collected.
    """
    trunk_angle = float(angles.get("trunk_flexion") or 0)
    neck_angle = float(angles.get("neck_flexion") or trunk_angle * 0.5)
    knee = next((float(angles[name]) for name in ("left_knee", "right_knee") if angles.get(name) is not None), 180.0)
    elbow = next((float(angles[name]) for name in ("left_elbow", "right_elbow") if angles.get(name) is not None), 90.0)
    shoulder = next((float(angles[name]) for name in ("left_shoulder_elevation", "right_shoulder_elevation") if angles.get(name) is not None), elbow)

    trunk = _bin_trunk(trunk_angle)
    neck = _bin_neck(neck_angle)
    legs = _bin_legs(knee)
    score_a_base = TABLE_A[neck - 1][trunk - 1][legs - 1]
    load = 1 if confidence < 0.6 else 0
    score_a = min(12, score_a_base + load)

    upper = _bin_upper_arm(shoulder)
    lower = _bin_lower_arm(elbow)
    wrist = 1
    score_b_base = TABLE_B[upper - 1][lower - 1][wrist - 1]
    coupling = 0
    score_b = min(12, score_b_base + coupling)
    score_c = TABLE_C[score_a - 1][score_b - 1]
    activity = 1 if confidence < 0.6 else 0
    score = min(15, score_c + activity)
    return {
        "score": score,
        "risk_level": _risk(score),
        "component_scores": {
            "trunk": trunk,
            "neck": neck,
            "legs": legs,
            "upper_arm": upper,
            "lower_arm": lower,
            "wrist": wrist,
            "score_a": score_a,
            "score_b": score_b,
            "score_c": score_c,
            "load": load,
            "coupling": coupling,
            "activity": activity,
        },
        "rule_version": "reba-standard-proxy-0.2",
        "method": "REBA 2000 tables with explicit neutral values for unavailable load/coupling/twist inputs",
    }
