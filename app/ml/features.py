import numpy as np

from app.core.exceptions import SignalRejectedError


FEATURE_NAMES = [
    "mean_rr", "median_rr", "mean_hr", "min_hr", "max_hr", "sdnn",
    "rmssd", "pnn50", "rr_range", "rr_cv", "mean_abs_rr_diff",
    "std_rr_diff", "hr_std",
]


def extract_hrv_features(rpeaks: np.ndarray, fs: int, rr_min_ms: float = 300, rr_max_ms: float = 2000,
                        minimum_rr_valid_ratio: float = 0.8, minimum_rpeaks: int = 20) -> tuple[dict[str, float], dict[str, float | int]]:
    if len(rpeaks) < minimum_rpeaks:
        raise SignalRejectedError("TOO_FEW_RPEAKS", f"At least {minimum_rpeaks} R-peaks are required.")
    rr_ms = np.diff(rpeaks) / fs * 1000.0
    if len(rr_ms) < 2:
        raise SignalRejectedError("INSUFFICIENT_RR", "The ECG does not contain enough RR intervals.")
    valid_mask = (rr_ms >= rr_min_ms) & (rr_ms <= rr_max_ms)
    rr_valid = rr_ms[valid_mask]
    valid_ratio = len(rr_valid) / len(rr_ms)
    if len(rr_valid) < 2:
        raise SignalRejectedError("INSUFFICIENT_VALID_RR", "Fewer than two valid RR intervals remain.")
    if valid_ratio < minimum_rr_valid_ratio:
        raise SignalRejectedError("LOW_RR_VALID_RATIO", "The RR interval valid ratio is below the required threshold.")
    pair_valid = valid_mask[:-1] & valid_mask[1:]
    rr_diff_valid = np.diff(rr_ms)[pair_valid]
    if len(rr_diff_valid) == 0:
        raise SignalRejectedError("NO_VALID_RR_DIFFERENCES", "No valid successive RR differences remain.")
    instantaneous_hr = 60000.0 / rr_valid
    sdnn = float(np.std(rr_valid, ddof=1))
    features = {
        "mean_rr": float(np.mean(rr_valid)), "median_rr": float(np.median(rr_valid)),
        "mean_hr": float(np.mean(instantaneous_hr)), "min_hr": float(np.min(instantaneous_hr)),
        "max_hr": float(np.max(instantaneous_hr)), "sdnn": sdnn,
        "rmssd": float(np.sqrt(np.mean(rr_diff_valid ** 2))),
        "pnn50": float(np.sum(np.abs(rr_diff_valid) > 50) / len(rr_diff_valid) * 100),
        "rr_range": float(np.max(rr_valid) - np.min(rr_valid)), "rr_cv": float(sdnn / np.mean(rr_valid)),
        "mean_abs_rr_diff": float(np.mean(np.abs(rr_diff_valid))),
        "std_rr_diff": float(np.std(rr_diff_valid, ddof=1)) if len(rr_diff_valid) > 1 else 0.0,
        "hr_std": float(np.std(instantaneous_hr, ddof=1)) if len(instantaneous_hr) > 1 else 0.0,
    }
    if not np.all(np.isfinite(list(features.values()))):
        raise SignalRejectedError("NONFINITE_FEATURES", "Feature extraction produced non-finite values.")
    quality = {"n_rpeaks": len(rpeaks), "n_rr_total": len(rr_ms), "n_rr_valid": len(rr_valid), "rr_valid_ratio": float(valid_ratio)}
    return features, quality