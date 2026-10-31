from typing import Any

import numpy as np

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, MathematicalExplanationError, ModelUnavailableError
from app.ml.inference import predict_apnea_from_ecg
from app.ml.model_loader import ModelPackage
from app.schemas.responses import AIExplanationStatus
from app.services.ai_explanation_service import (
    RecordingEvidenceError,
    build_recording_context,
    safe_generate_ai_explanation,
)


def analyze_ecg_recording(
    signal: Any,
    fs: int,
    package: ModelPackage,
    include_features: bool = False,
    include_explanation: bool = False,
    include_ai_explanation: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    if fs != package.sampling_rate:
        raise AppError("INVALID_SAMPLE_RATE", "The current model was validated for 100 Hz ECG input. Automatic resampling is not enabled in this version.", 422)
    values = np.asarray(signal, dtype=float)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise AppError("INVALID_SIGNAL", "The ECG must be non-empty and contain only finite values.", 422)
    window_size = package.sampling_rate * package.window_seconds
    total_windows = values.size // window_size
    ignored_samples = values.size % window_size
    windows = []
    mathematical_explanation_unavailable = False
    for index in range(total_windows):
        start = index * window_size
        try:
            window_values = values[start:start + window_size]
            try:
                result = predict_apnea_from_ecg(
                    window_values,
                    package,
                    include_features=include_features,
                    include_explanation=include_explanation or include_ai_explanation,
                )
            except MathematicalExplanationError:
                if not include_ai_explanation:
                    raise
                mathematical_explanation_unavailable = True
                result = predict_apnea_from_ecg(
                    window_values,
                    package,
                    include_features=include_features,
                    include_explanation=False,
                )
            windows.append({"window_index": index, "start_second": index * package.window_seconds, "end_second": (index + 1) * package.window_seconds, **result})
        except ModelUnavailableError:
            raise
        except AppError as exc:
            if exc.code == "MODEL_PREDICTION_FAILED":
                raise
            windows.append({"window_index": index, "start_second": index * package.window_seconds, "end_second": (index + 1) * package.window_seconds, "status": "rejected", "error": {"code": exc.code, "message": exc.message}})
    successful = [window for window in windows if window["status"] == "success"]
    apnea_count = sum(window["result"]["class"] == "A" for window in successful)
    valid_count = len(successful)
    summary = {"total_windows": total_windows, "valid_windows": valid_count, "rejected_windows": len(windows) - valid_count, "apnea_pattern_windows": apnea_count, "normal_pattern_windows": valid_count - apnea_count, "apnea_window_percentage": (apnea_count / valid_count * 100) if valid_count else 0.0, "mean_apnea_class_score": float(np.mean([window["result"]["apnea_class_score"] for window in successful])) if successful else None}
    response = {"status": "success", "model_version": package.model_version, "summary": summary, "ignored_samples": ignored_samples, "ignored_seconds": ignored_samples / package.sampling_rate, "windows": windows}
    if include_ai_explanation:
        if mathematical_explanation_unavailable or any("explanation" not in window for window in successful):
            ai_explanation = None
            ai_status = AIExplanationStatus(status="unavailable", code="mathematical_explanation_unavailable")
        elif not successful:
            ai_explanation = None
            ai_status = AIExplanationStatus(status="unavailable", code="insufficient_successful_windows")
        else:
            try:
                context = build_recording_context(package.model_version, summary, windows)
            except RecordingEvidenceError:
                ai_explanation = None
                ai_status = AIExplanationStatus(
                    status="unavailable",
                    code="inconsistent_mathematical_evidence",
                )
            else:
                ai_explanation, ai_status = safe_generate_ai_explanation(
                    context,
                    settings or get_settings(),
                )
        response["ai_explanation"] = ai_explanation.model_dump() if ai_explanation else None
        response["ai_explanation_status"] = ai_status.model_dump()
    if not include_explanation:
        for window in successful:
            window.pop("explanation", None)
    return response
