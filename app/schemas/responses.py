from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    status: str = "error"
    code: str
    message: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str | None = None


class ModelInfoResponse(BaseModel):
    model_version: str
    sampling_rate: int
    window_seconds: int
    required_samples: int
    feature_count: int
    threshold: float
    supported_file_types: list[str]


class SignalQuality(BaseModel):
    n_rpeaks: int
    n_rr_total: int
    n_rr_valid: int
    rr_valid_ratio: float


class PredictionResponse(BaseModel):
    status: str
    model_version: str
    window: dict[str, Any]
    result: dict[str, Any]
    signal_quality: SignalQuality
    features: dict[str, float] | None = None


class RecordingAnalysisResponse(BaseModel):
    status: str
    model_version: str
    summary: dict[str, Any]
    ignored_samples: int
    ignored_seconds: float
    windows: list[dict[str, Any]]