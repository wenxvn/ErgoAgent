from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

class Keypoint2D(BaseModel):
    x: float | None
    y: float | None
    confidence: float = Field(ge=0, le=1)

class Pose2D(BaseModel):
    format: str
    coordinate_space: str
    frame_width: int = Field(gt=0)
    frame_height: int = Field(gt=0)
    keypoints: dict[str, Keypoint2D]

class Keypoint3D(BaseModel):
    x: float | None
    y: float | None
    z: float | None
    confidence: float = Field(ge=0, le=1)

class Pose3D(BaseModel):
    format: str
    coordinate_space: str
    unit: str
    keypoints: dict[str, Keypoint3D]

class Angle(BaseModel):
    degrees: float | None
    confidence: float = Field(ge=0, le=1)
    source_keypoints: list[str]

class Reba(BaseModel):
    score: int = Field(ge=1, le=15)
    risk_level: Literal['negligible','low','medium','high','very_high']
    component_scores: dict[str, int | None]
    rule_version: str

class FramePayload(BaseModel):
    bbox: dict
    pose_2d: Pose2D
    pose_3d: Pose3D | None = None
    confidence: float = Field(ge=0, le=1)
    angles: dict[str, Angle]
    reba: Reba

class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = {}

class ErrorResponse(BaseModel):
    error: ErrorBody
