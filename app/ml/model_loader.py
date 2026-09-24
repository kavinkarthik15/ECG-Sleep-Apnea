from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

from app.core.exceptions import ModelUnavailableError
from app.ml.features import FEATURE_NAMES


@dataclass(frozen=True)
class ModelPackage:
    model: Any
    feature_names: list[str]
    threshold: float
    sampling_rate: int
    window_seconds: int
    filter_lowcut: float
    filter_highcut: float
    filter_order: int
    rr_min_ms: float
    rr_max_ms: float
    minimum_rr_valid_ratio: float
    minimum_rpeaks: int
    rpeak_method: str
    class_mapping: dict[Any, Any]
    model_version: str


def load_model_package(path: Path) -> ModelPackage:
    if not path.is_file():
        raise ModelUnavailableError(f"Model artifact is missing: {path.name}")
    try:
        package = joblib.load(path)
    except Exception as exc:
        raise ModelUnavailableError("The model artifact could not be loaded.") from exc
    required = {"model", "feature_names", "threshold", "sampling_rate", "window_seconds", "filter_lowcut", "filter_highcut", "filter_order", "rr_min_ms", "rr_max_ms", "minimum_rr_valid_ratio", "minimum_rpeaks", "rpeak_method", "class_mapping", "model_version"}
    if not isinstance(package, dict) or not required.issubset(package):
        raise ModelUnavailableError("The model artifact is missing required metadata.")
    if list(package["feature_names"]) != FEATURE_NAMES or package["sampling_rate"] != 100 or package["window_seconds"] != 60:
        raise ModelUnavailableError("The model artifact metadata is incompatible with this backend.")
    return ModelPackage(**{key: package[key] for key in required})