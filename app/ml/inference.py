from typing import Any

import neurokit2 as nk
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.core.exceptions import MathematicalExplanationError, SignalRejectedError
from app.ml.features import FEATURE_NAMES, extract_hrv_features
from app.ml.model_loader import ModelPackage
from app.ml.preprocessing import bandpass_filter_ecg


def _calculate_explanation(features: dict[str, Any], package: ModelPackage) -> dict[str, Any]:
    def incompatible(message: str) -> MathematicalExplanationError:
        return MathematicalExplanationError(f"Cannot calculate a Logistic Regression explanation: {message}")

    if not isinstance(package.model, Pipeline) or list(package.model.named_steps) != ["scaler", "classifier"]:
        raise incompatible("the model must be a fitted scaler/classifier pipeline.")
    scaler = package.model.named_steps["scaler"]
    classifier = package.model.named_steps["classifier"]
    if not isinstance(scaler, StandardScaler) or not isinstance(classifier, LogisticRegression):
        raise incompatible("the pipeline must contain StandardScaler and LogisticRegression steps.")

    expected_names = list(package.feature_names)
    if expected_names != FEATURE_NAMES or list(features) != expected_names:
        raise incompatible("feature names or feature order do not match the model.")
    model_names = getattr(package.model, "feature_names_in_", None)
    scaler_names = getattr(scaler, "feature_names_in_", None)
    if model_names is None or scaler_names is None or list(model_names) != expected_names or list(scaler_names) != expected_names:
        raise incompatible("the fitted model feature order does not match the package.")

    try:
        values = np.asarray([features[name] for name in expected_names], dtype=float)
        means = np.asarray(scaler.mean_, dtype=float)
        scales = np.asarray(scaler.scale_, dtype=float)
        coefficients = np.asarray(classifier.coef_, dtype=float)
        intercepts = np.asarray(classifier.intercept_, dtype=float)
        classes = np.asarray(classifier.classes_)
        pipeline_classes = np.asarray(package.model.classes_)
    except (AttributeError, TypeError, ValueError) as exc:
        raise incompatible("the fitted model is missing required numeric attributes.") from exc

    feature_count = len(expected_names)
    if (
        values.shape != (feature_count,)
        or means.shape != (feature_count,)
        or scales.shape != (feature_count,)
        or coefficients.ndim != 2
        or coefficients.shape[1] != feature_count
        or intercepts.shape != (coefficients.shape[0],)
        or classes.shape != (2,)
        or pipeline_classes.shape != classes.shape
        or not np.array_equal(classes, pipeline_classes)
        or set(classes.tolist()) != {0, 1}
    ):
        raise incompatible("the fitted model dimensions or classes do not match the expected binary model.")
    if package.class_mapping.get(1) != "A":
        raise incompatible("class 1 is not mapped to apnea (A).")
    if (
        not np.all(np.isfinite(values))
        or not np.all(np.isfinite(means))
        or not np.all(np.isfinite(scales))
        or not np.all(np.isfinite(coefficients))
        or not np.all(np.isfinite(intercepts))
        or np.any(scales == 0)
    ):
        raise incompatible("feature values or fitted parameters are non-finite or invalid.")

    class_1_index = int(np.flatnonzero(classes == 1)[0])
    if coefficients.shape[0] == len(classes):
        class_1_coefficients = coefficients[class_1_index]
        intercept = float(intercepts[class_1_index])
    elif coefficients.shape[0] == 1 and len(classes) == 2:
        # Binary LogisticRegression stores one row for classes_[1].
        sign = 1.0 if class_1_index == 1 else -1.0
        class_1_coefficients = coefficients[0] * sign
        intercept = float(intercepts[0] * sign)
    else:
        raise incompatible("the classifier coefficient rows cannot be aligned with class 1.")

    contributions = (values - means) * class_1_coefficients / scales
    logit = float(intercept + np.sum(contributions))
    if not np.all(np.isfinite(contributions)) or not np.isfinite(logit):
        raise incompatible("the calculated contributions or logit are non-finite.")
    if logit >= 0:
        probability = float(1.0 / (1.0 + np.exp(-logit)))
    else:
        exp_logit = np.exp(logit)
        probability = float(exp_logit / (1.0 + exp_logit))
    if not np.isfinite(probability):
        raise incompatible("the reconstructed probability is non-finite.")

    feature_df = pd.DataFrame([values], columns=expected_names)
    try:
        model_probabilities = np.asarray(package.model.predict_proba(feature_df), dtype=float)
    except Exception as exc:
        raise incompatible("the model could not verify the reconstructed probability.") from exc
    if (
        model_probabilities.shape != (1, len(classes))
        or not np.all(np.isfinite(model_probabilities))
        or not np.isclose(probability, model_probabilities[0, class_1_index], rtol=1e-12, atol=1e-15)
    ):
        raise incompatible("the reconstructed probability does not match the fitted model.")

    entries = []
    for name, value, contribution in zip(expected_names, values, contributions, strict=True):
        numeric_contribution = float(contribution)
        entries.append({
            "feature_name": name,
            "feature_value": float(value),
            "contribution": numeric_contribution,
            "direction": "toward_apnea" if numeric_contribution > 0 else "away_from_apnea" if numeric_contribution < 0 else "neutral",
        })
    entries.sort(key=lambda entry: abs(entry["contribution"]), reverse=True)
    return {
        "class_label": "A",
        "method": "logistic_regression_feature_contributions",
        "intercept": intercept,
        "logit": logit,
        "reconstructed_probability": probability,
        "features": entries,
    }


def predict_apnea_from_ecg(
    ecg_window: Any,
    package: ModelPackage,
    include_features: bool = False,
    include_explanation: bool = False,
) -> dict[str, Any]:
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
    if include_explanation:
        result["explanation"] = _calculate_explanation(features, package)
    return result
