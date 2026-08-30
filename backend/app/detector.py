from __future__ import annotations

import os
from typing import Any


def detector_mode() -> str:
    return os.getenv("ERGOAGENT_PERSON_DETECTOR", "mediapipe").strip().lower()


def detect_person_boxes(frame: Any, cv2_module: Any, mode: str | None = None) -> list[dict[str, float]]:
    """Return multiple person boxes for the optional OpenCV HOG detector.

    MediaPipe Pose remains the default because it is the verified MVP path.
    Setting ERGOAGENT_PERSON_DETECTOR=hog enables a real multi-person proposal
    stage without adding another model or downloading untracked weights.
    """
    selected = (mode or detector_mode())
    if selected not in {"hog", "opencv-hog"}:
        return []
    hog = cv2_module.HOGDescriptor()
    hog.setSVMDetector(cv2_module.HOGDescriptor_getDefaultPeopleDetector())
    height, width = frame.shape[:2]
    scale = min(1.0, 960.0 / max(width, height))
    image = frame if scale == 1.0 else cv2_module.resize(frame, (round(width * scale), round(height * scale)))
    boxes, weights = hog.detectMultiScale(image, winStride=(8, 8), padding=(8, 8), scale=1.05)
    candidates: list[dict[str, float]] = []
    for (x, y, w, h), weight in zip(boxes, weights):
        if float(weight) < 0.7 or w < 24 or h < 48:
            continue
        inv = 1 / scale
        candidates.append({"x": float(x * inv), "y": float(y * inv), "width": float(w * inv), "height": float(h * inv), "detector_confidence": float(weight)})

    # OpenCV HOG commonly returns several overlapping windows for one person.
    # Greedy IoU suppression keeps the detector output suitable for tracking.
    kept: list[dict[str, float]] = []
    for candidate in sorted(candidates, key=lambda item: item["detector_confidence"], reverse=True):
        def overlap(other: dict[str, float]) -> float:
            left = max(candidate["x"], other["x"])
            top = max(candidate["y"], other["y"])
            right = min(candidate["x"] + candidate["width"], other["x"] + other["width"])
            bottom = min(candidate["y"] + candidate["height"], other["y"] + other["height"])
            intersection = max(0.0, right - left) * max(0.0, bottom - top)
            union = candidate["width"] * candidate["height"] + other["width"] * other["height"] - intersection
            return intersection / union if union else 0.0
        if all(overlap(existing) < 0.45 for existing in kept):
            kept.append(candidate)
    return kept
