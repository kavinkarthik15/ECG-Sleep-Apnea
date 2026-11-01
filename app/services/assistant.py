from typing import Any, Protocol


FEATURE_GUIDANCE = {
    "mean_rr": ("Mean RR interval", "ms", "the arithmetic mean of valid RR intervals"),
    "median_rr": ("Median RR interval", "ms", "the median of valid RR intervals"),
    "mean_hr": ("Mean heart rate", "bpm", "the mean of rates calculated from valid RR intervals"),
    "min_hr": ("Minimum heart rate", "bpm", "the minimum rate calculated from valid RR intervals"),
    "max_hr": ("Maximum heart rate", "bpm", "the maximum rate calculated from valid RR intervals"),
    "sdnn": ("SDNN", "ms", "the sample standard deviation of valid RR intervals"),
    "rmssd": ("RMSSD", "ms", "the root mean square of valid successive RR differences"),
    "pnn50": ("pNN50", "%", "the percentage of valid successive RR differences over 50 ms"),
    "rr_range": ("RR range", "ms", "the difference between the largest and smallest valid RR intervals"),
    "rr_cv": ("RR coefficient of variation", "ratio", "SDNN divided by mean RR"),
    "mean_abs_rr_diff": ("Mean absolute RR difference", "ms", "the mean absolute valid successive RR difference"),
    "std_rr_diff": ("RR-difference standard deviation", "ms", "the sample standard deviation of valid successive RR differences"),
    "hr_std": ("Heart-rate standard deviation", "bpm", "the sample standard deviation of rates calculated from valid RR intervals"),
}


class AssistantProvider(Protocol):
    def answer(self, question: str, context: dict[str, Any]) -> str: ...


class LocalContextAssistant:
    def answer(self, question: str, context: dict[str, Any]) -> str:
        normalized = question.casefold()
        selected_window = context.get("selected_window")
        selected_peak = context.get("selected_peak")
        interval = context.get("selected_interval")
        selected_feature = context.get("selected_feature")
        summary = context["summary"]

        if any(term in normalized for term in ("diagnos", "treatment", "should i take", "do i have")):
            return (
                "This academic screening prototype cannot diagnose a condition or recommend "
                "treatment. Please discuss health concerns with a qualified clinician."
            )

        if any(term in normalized for term in ("peak", "r-peak", "r peak")):
            if selected_peak is None:
                return "Select a detected R-peak in the waveform to see its recorded sample index and timestamp."
            return (
                f"The selected detected R-peak is at recording sample "
                f"{selected_peak['recording_sample_index']} ({selected_peak['timestamp_seconds']:.2f} s) "
                f"in window {selected_peak['window_index'] + 1}. These are detector locations, "
                "not a separate clinical measurement."
            )

        if any(term in normalized for term in ("what is hrv", "meaning of hrv", "define hrv")):
            return (
                "Heart-rate variability (HRV) describes changes in the time between successive "
                "detected beats. This pipeline derives its listed HRV features from valid RR "
                "intervals in each accepted 60-second window; the measurements are descriptive "
                "and are not interpreted as a diagnosis."
            )

        if any(term in normalized for term in ("what is ecg", "what is an ecg", "electrocardiogram")):
            return (
                "An electrocardiogram (ECG) is a recording of electrical signal over time. This "
                "prototype displays a bounded envelope of the submitted single-channel samples "
                "and analyzes consecutive 60-second windows at the configured 100 Hz sampling "
                "rate. It is not a clinical ECG interpretation."
            )

        features_to_explain = list(FEATURE_GUIDANCE)
        if selected_feature in FEATURE_GUIDANCE:
            features_to_explain.remove(selected_feature)
            features_to_explain.insert(0, selected_feature)
        for feature in features_to_explain:
            label, unit, definition = FEATURE_GUIDANCE[feature]
            if (
                feature.replace("_", " ") in normalized
                or label.casefold() in normalized
                or (feature == selected_feature and any(term in normalized for term in ("explain", "this", "selected")))
            ):
                if selected_window is None or selected_window["status"] != "success":
                    return f"{label} is unavailable for the selected window."
                value = selected_window.get("features", {}).get(feature)
                if value is None:
                    return f"{label} was not included in the saved analysis for this window."
                return (
                    f"{label} for window {selected_window['window_index'] + 1} is "
                    f"{value:.4g} {unit}. In this pipeline, it is {definition}. "
                    "This value is descriptive and is not interpreted here as a diagnosis."
                )

        if any(term in normalized for term in ("quality", "rejected", "valid rr", "signal")):
            if selected_window is None:
                return (
                    f"The recording contains {summary['valid_windows']} accepted and "
                    f"{summary['rejected_windows']} rejected windows out of "
                    f"{summary['total_windows']}. Select a window to inspect its available "
                    "signal-quality counts or rejection reason."
                )
            if selected_window["status"] == "rejected":
                reason = selected_window.get("error", {}).get("message", "No rejection details were saved.")
                return f"Window {selected_window['window_index'] + 1} was rejected: {reason}"
            quality = selected_window.get("signal_quality")
            if quality is None:
                return "Signal-quality information is unavailable for this window."
            return (
                f"Window {selected_window['window_index'] + 1} has "
                f"{quality['n_rpeaks']} detected R-peaks and "
                f"{quality['n_rr_valid']} valid of {quality['n_rr_total']} RR intervals "
                f"({quality['rr_valid_ratio'] * 100:.1f}% valid). These are the saved pipeline values."
            )

        if interval is not None or any(term in normalized for term in ("waveform", "interval", "selected region")):
            if interval is None:
                return "Select a time interval in the waveform to inspect its recording-relative time range."
            envelope = interval.get("display_envelope_range")
            envelope_summary = (
                f" The retained display-envelope points in that interval range from "
                f"{envelope['minimum']:.5g} to {envelope['maximum']:.5g} in the source amplitude "
                f"units ({envelope['point_count']} points); this is not a full-resolution "
                "statistic."
                if envelope is not None
                else " No retained envelope points fall inside that selected interval."
            )
            return (
                f"The selected interval spans {interval['start_seconds']:.2f}–"
                f"{interval['end_seconds']:.2f} seconds in the recording "
                f"(window {interval['window_index'] + 1}). The displayed waveform is a bounded "
                "min/max envelope of the uploaded samples; raw ECG samples are not retained."
                + envelope_summary
            )

        if selected_window is not None and any(
            term in normalized for term in ("window", "score", "class", "result", "pattern")
        ):
            if selected_window["status"] == "rejected":
                reason = selected_window.get("error", {}).get("message", "No rejection details were saved.")
                return f"Window {selected_window['window_index'] + 1} was rejected: {reason}"
            result = selected_window.get("result", {})
            return (
                f"Window {selected_window['window_index'] + 1} was accepted and mapped to class "
                f"{result.get('class')} by the existing model, with an apnea-class score of "
                f"{result.get('apnea_class_score', 0):.4f} and threshold "
                f"{result.get('threshold', 0):.4f}. The score is a model output, not a clinical "
                "probability or diagnosis."
            )

        if any(term in normalized for term in ("model", "limit", "class mapping", "screening")):
            return (
                f"The saved screening summary reports {summary['apnea_pattern_windows']} "
                f"apnea-related-pattern windows among {summary['valid_windows']} accepted windows; "
                f"{summary['rejected_windows']} windows were rejected. Class A maps to the "
                "apnea-related pattern and class N to the other model class. This research output "
                "is not a medical diagnosis, AHI estimate, or severity classification."
            )

        return (
            "I can explain the selected window's saved screening output, HRV features, signal "
            "quality, detected R-peaks, or a selected waveform interval. I use a local, "
            "rule-based guide rather than a generative AI model; select a context or ask about "
            "one of those saved measurements."
        )


def build_analysis_context(
    record: Any,
    *,
    window_index: int | None,
    interval_start_sample: int | None,
    interval_end_sample: int | None,
    peak_sample: int | None,
    selected_feature: str | None,
) -> dict[str, Any]:
    windows = record.windows
    selected_window = None
    if window_index is not None:
        selected_window = next(
            (window for window in windows if window["window_index"] == window_index),
            None,
        )
        if selected_window is None:
            raise ValueError("Selected analysis window does not exist.")

    if (interval_start_sample is None) != (interval_end_sample is None):
        raise ValueError("Both interval sample bounds are required.")
    if (
        interval_start_sample is not None
        or peak_sample is not None
        or selected_feature is not None
    ) and selected_window is None:
        raise ValueError("A selected window is required for waveform context.")

    interval = None
    peak = None
    if selected_window is not None:
        window_samples = record.sampling_rate * record.window_seconds
        if selected_feature is not None and selected_feature not in selected_window.get("features", {}):
            raise ValueError("Selected HRV feature is unavailable in this window.")
        if interval_start_sample is not None:
            if not 0 <= interval_start_sample < interval_end_sample <= window_samples:
                raise ValueError("Selected waveform interval is outside the window.")
            interval = {
                "window_index": window_index,
                "start_seconds": selected_window["start_second"]
                + interval_start_sample / record.sampling_rate,
                "end_seconds": selected_window["start_second"]
                + interval_end_sample / record.sampling_rate,
            }
            display_values = [
                point["value"]
                for point in selected_window.get("waveform", [])
                if interval_start_sample <= point["sample_index"] <= interval_end_sample
            ]
            if display_values:
                interval["display_envelope_range"] = {
                    "minimum": min(display_values),
                    "maximum": max(display_values),
                    "point_count": len(display_values),
                }
        if peak_sample is not None:
            if peak_sample not in selected_window.get("rpeak_samples", []):
                raise ValueError("Selected sample is not a detected R-peak in this window.")
            peak = {
                "window_index": window_index,
                "recording_sample_index": window_index * window_samples + peak_sample,
                "timestamp_seconds": selected_window["start_second"]
                + peak_sample / record.sampling_rate,
            }

    return {
        "summary": record.summary,
        "selected_window": selected_window,
        "selected_interval": interval,
        "selected_peak": peak,
        "selected_feature": selected_feature,
    }


def get_assistant_provider() -> AssistantProvider:
    return LocalContextAssistant()
