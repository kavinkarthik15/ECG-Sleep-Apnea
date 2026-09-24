from typing import Any

import neurokit2 as nk
import numpy as np
import pandas as pd

from app.core.exceptions import SignalRejectedError
from app.ml.features import FEATURE_NAMES, extract_hrv_features
from app.ml.model_loader import ModelPackage
from app.ml.preprocessing import bandpass_filter_ecg


def predict_apnea_from_ecg(ecg_window: Any, package: ModelPackage, include_features: bool = False) -> dict[str, Any]:
    signal = np.asarray(ecg_window, dtype=float)
    expected = package.sampling_rate * package.window_seconds
    if signal.size != expected:
        raise SignalRejectedError("INVALID_SAMPLE_COUNT", f"Exactly {expected} samples are required.")
    if signal.size == 0 or not np.all(np.isfinite(signal)):
        raise SignalRejectedError("INVALID_SIGNAL", "The ECG must be non-empty and contain only finite values.")
    if float(np.std(signal)) < 1e-6:
        raise SignalRejectedError("FLAT_SIGNAL", "The ECG signal has insufficient variation.")
    try:
        filtered = bandpass_filter_ecg(signal, package.sampling_rate, package.filter_lowcut, package.filter_highcut, package.filter_order)
        _, info = nk.ecg_peaks(filtered, sampling_rate=package.sampling_rate, method=package.rpeak_method)
        rpeaks = np.asarray(info["ECG_R_Peaks"])
    except Exception as exc:
        raise SignalRejectedError("RPEAK_DETECTION_FAILED", "R-peak detection failed for this ECG window.") from exc
    features, quality = extract_hrv_features(rpeaks, package.sampling_rate, package.rr_min_ms, package.rr_max_ms, package.minimum_rr_valid_ratio, package.minimum_rpeaks)
    feature_df = pd.DataFrame([[features[name] for name in package.feature_names]], columns=package.feature_names)
    try:
        probability = float(package.model.predict_proba(feature_df)[0, 1])
    except Exception as exc:
        raise SignalRejectedError("MODEL_PREDICTION_FAILED", "The model could not process this ECG window.") from exc
    is_apnea = probability >= package.threshold
    result = {"status": "success", "model_version": package.model_version, "window": {"duration_seconds": package.window_seconds, "sampling_rate": package.sampling_rate, "samples": expected}, "result": {"class": "A" if is_apnea else "N", "label": "Apnea-related pattern detected" if is_apnea else "No apnea-related pattern detected", "apnea_class_score": probability, "threshold": package.threshold}, "signal_quality": quality}
    if include_features:
        result["features"] = features
    return result