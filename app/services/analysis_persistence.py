import secrets
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.persistence import ECGAnalysis, VisitorSession

MAX_WAVEFORM_POINTS_PER_WINDOW = 1200


def attach_waveform_envelopes(
    response: dict[str, Any],
    signal: Any,
    sampling_rate: int,
    window_seconds: int,
) -> None:
    samples = np.asarray(signal, dtype=float)
    window_size = sampling_rate * window_seconds
    for window in response["windows"]:
        start = window["window_index"] * window_size
        segment = samples[start : start + window_size]
        bucket_count = min(len(segment), max(0, (MAX_WAVEFORM_POINTS_PER_WINDOW - 2) // 2))
        if len(segment) == 0:
            window["waveform"] = []
            continue

        points_by_index = {
            0: float(segment[0]),
            len(segment) - 1: float(segment[-1]),
        }
        for bucket in range(bucket_count):
            left = bucket * len(segment) // bucket_count
            right = (bucket + 1) * len(segment) // bucket_count
            values = segment[left:right]
            min_index = left + int(np.argmin(values))
            max_index = left + int(np.argmax(values))
            for sample_index in sorted({min_index, max_index}):
                points_by_index[sample_index] = float(segment[sample_index])
        window["waveform"] = [
            {"sample_index": sample_index, "value": value}
            for sample_index, value in sorted(points_by_index.items())
        ]


def persist_analysis(
    db: Session,
    visitor_session: VisitorSession,
    response: dict[str, Any],
    sampling_rate: int,
    window_seconds: int,
) -> str:
    reference = secrets.token_urlsafe(32)
    stored_windows = []
    for window in response["windows"]:
        stored_window = dict(window)
        if "rpeak_samples" in stored_window:
            stored_window["rpeak_samples"] = [int(sample) for sample in stored_window["rpeak_samples"]]
        stored_windows.append(stored_window)

    record = ECGAnalysis(
        public_ref=reference,
        visitor_session_id=visitor_session.id,
        created_at=datetime.now(timezone.utc),
        model_version=response["model_version"],
        sampling_rate=sampling_rate,
        window_seconds=window_seconds,
        ignored_samples=response["ignored_samples"],
        ignored_seconds=response["ignored_seconds"],
        summary=response["summary"],
        windows=stored_windows,
    )
    with db.begin():
        db.add(record)
        db.flush()
    return reference


def analysis_response(record: ECGAnalysis) -> dict[str, Any]:
    windows = []
    for window in record.windows:
        windows.append(
            {
                key: value
                for key, value in window.items()
                if key not in {"waveform", "rpeak_samples"}
            }
        )
    return {
        "status": "success",
        "model_version": record.model_version,
        "summary": record.summary,
        "ignored_samples": record.ignored_samples,
        "ignored_seconds": record.ignored_seconds,
        "windows": windows,
        "analysis_ref": record.public_ref,
    }


def analysis_window_response(
    record: ECGAnalysis,
    window_index: int,
) -> dict[str, Any]:
    window = next(
        (item for item in record.windows if item["window_index"] == window_index),
        None,
    )
    if window is None:
        raise AppError("ANALYSIS_WINDOW_NOT_FOUND", "The requested analysis window was not found.", 404)
    return {
        "window": dict(window),
        "sampling_rate": record.sampling_rate,
        "window_seconds": record.window_seconds,
    }


def get_latest_analysis(db: Session, visitor_session: VisitorSession) -> ECGAnalysis | None:
    return db.scalar(
        select(ECGAnalysis)
        .where(ECGAnalysis.visitor_session_id == visitor_session.id)
        .order_by(ECGAnalysis.created_at.desc(), ECGAnalysis.id.desc())
        .limit(1)
    )


def get_owned_analysis(
    db: Session,
    visitor_session: VisitorSession,
    public_ref: str,
) -> ECGAnalysis:
    record = db.scalar(
        select(ECGAnalysis).where(
            ECGAnalysis.public_ref == public_ref,
            ECGAnalysis.visitor_session_id == visitor_session.id,
        )
    )
    if record is None:
        raise AppError("ANALYSIS_NOT_FOUND", "The requested analysis was not found.", 404)
    return record
