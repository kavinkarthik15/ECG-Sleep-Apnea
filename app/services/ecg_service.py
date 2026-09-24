from typing import Any

import numpy as np

from app.core.exceptions import AppError
from app.ml.inference import predict_apnea_from_ecg
from app.ml.model_loader import ModelPackage


def analyze_ecg_recording(signal: Any, fs: int, package: ModelPackage, include_features: bool = False) -> dict[str, Any]:
    if fs != package.sampling_rate:
        raise AppError("INVALID_SAMPLE_RATE", "The current model was validated for 100 Hz ECG input. Automatic resampling is not enabled in this version.", 422)
    values = np.asarray(signal, dtype=float)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise AppError("INVALID_SIGNAL", "The ECG must be non-empty and contain only finite values.", 422)
    window_size = package.sampling_rate * package.window_seconds
    total_windows = values.size // window_size
    ignored_samples = values.size % window_size
    windows = []
    for index in range(total_windows):
        start = index * window_size
        try:
            result = predict_apnea_from_ecg(values[start:start + window_size], package, include_features)
            windows.append({"window_index": index, "start_second": index * package.window_seconds, "end_second": (index + 1) * package.window_seconds, **result})
        except AppError as exc:
            windows.append({"window_index": index, "start_second": index * package.window_seconds, "end_second": (index + 1) * package.window_seconds, "status": "rejected", "error": {"code": exc.code, "message": exc.message}})
    successful = [window for window in windows if window["status"] == "success"]
    apnea_count = sum(window["result"]["class"] == "A" for window in successful)
    valid_count = len(successful)
    return {"status": "success", "model_version": package.model_version, "summary": {"total_windows": total_windows, "valid_windows": valid_count, "rejected_windows": len(windows) - valid_count, "apnea_pattern_windows": apnea_count, "normal_pattern_windows": valid_count - apnea_count, "apnea_window_percentage": (apnea_count / valid_count * 100) if valid_count else 0.0, "mean_apnea_class_score": float(np.mean([window["result"]["apnea_class_score"] for window in successful])) if successful else None}, "ignored_samples": ignored_samples, "ignored_seconds": ignored_samples / package.sampling_rate, "windows": windows}