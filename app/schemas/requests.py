from pydantic import BaseModel, ConfigDict, Field


class ECGPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sampling_rate: int = Field(..., examples=[100])
    ecg_samples: list[float] = Field(..., min_length=1)
    include_features: bool = False


class LongECGRequest(ECGPredictionRequest):
    pass