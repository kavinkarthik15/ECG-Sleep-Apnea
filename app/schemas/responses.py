from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class FeatureContribution(BaseModel):
    feature_name: str
    feature_value: float
    contribution: float
    direction: Literal["toward_apnea", "away_from_apnea", "neutral"]


class PredictionExplanation(BaseModel):
    class_label: str
    method: str
    intercept: float
    logit: float
    reconstructed_probability: float
    features: list[FeatureContribution]


AI_EXPLANATION_DISCLAIMER = (
    "Experimental academic screening prototype; not a diagnostic device. "
    "The apnea-class score is not a patient's probability of having sleep apnea."
)


class AIExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1200)
    supporting_factors: list[str] = Field(max_length=5)
    opposing_factors: list[str] = Field(max_length=5)
    limitations: list[str] = Field(min_length=1, max_length=5)
    disclaimer: Literal[AI_EXPLANATION_DISCLAIMER]


class GeneratedAIExplanation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    headline: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1200)
    supporting_factors: list[str] = Field(max_length=5)
    opposing_factors: list[str] = Field(max_length=5)
    limitations: list[str] = Field(min_length=1, max_length=5)


class AIExplanationStatus(BaseModel):
    status: Literal["available", "unavailable"]
    code: str | None = None


class PredictionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    model_version: str
    window: dict[str, Any]
    result: dict[str, Any]
    signal_quality: SignalQuality
    features: dict[str, float] | None = None
    explanation: PredictionExplanation | None = None
    ai_explanation: AIExplanation | None = None
    ai_explanation_status: AIExplanationStatus | None = None


class RecordingAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    model_version: str
    summary: dict[str, Any]
    ignored_samples: int
    ignored_seconds: float
    windows: list[dict[str, Any]]
    ai_explanation: AIExplanation | None = None
    ai_explanation_status: AIExplanationStatus | None = None