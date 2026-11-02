from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

HRVFeatureName = Literal[
    "mean_rr",
    "median_rr",
    "mean_hr",
    "min_hr",
    "max_hr",
    "sdnn",
    "rmssd",
    "pnn50",
    "rr_range",
    "rr_cv",
    "mean_abs_rr_diff",
    "std_rr_diff",
    "hr_std",
]


class ECGPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sampling_rate: int = Field(..., examples=[100])
    ecg_samples: list[float] = Field(..., min_length=1)
    include_features: bool = False


class LongECGRequest(ECGPredictionRequest):
    pass


class AssistantMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_ref: str | None = Field(default=None, min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=1000)
    history: list["AssistantHistoryMessage"] = Field(default_factory=list, max_length=12)
    window_index: int | None = Field(default=None, ge=0)
    interval_start_sample: int | None = Field(default=None, ge=0)
    interval_end_sample: int | None = Field(default=None, ge=1)
    peak_sample: int | None = Field(default=None, ge=0)
    selected_feature: HRVFeatureName | None = None

    @model_validator(mode="after")
    def validate_interval_bounds(self) -> "AssistantMessageRequest":
        if (self.interval_start_sample is None) != (self.interval_end_sample is None):
            raise ValueError("Both interval sample bounds are required.")
        if (
            self.interval_start_sample is not None
            and self.interval_end_sample is not None
            and self.interval_end_sample <= self.interval_start_sample
        ):
            raise ValueError("Interval end must be after interval start.")
        if self.analysis_ref is None and any(
            value is not None
            for value in (
                self.window_index,
                self.interval_start_sample,
                self.interval_end_sample,
                self.peak_sample,
                self.selected_feature,
            )
        ):
            raise ValueError("Analysis context requires an analysis reference.")
        return self


class AssistantHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)