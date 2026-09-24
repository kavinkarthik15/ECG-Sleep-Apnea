import csv
import io
from pathlib import Path

import numpy as np

from app.core.exceptions import AppError


def parse_ecg_file(filename: str, content: bytes, max_bytes: int) -> np.ndarray:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".txt"}:
        raise AppError("UNSUPPORTED_FILE_TYPE", "Only .csv and .txt ECG files are supported.", 415)
    if len(content) > max_bytes:
        raise AppError("FILE_TOO_LARGE", "The uploaded file exceeds the maximum allowed size.", 413)
    try:
        rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise AppError("MALFORMED_FILE", "The ECG file could not be parsed.", 422) from exc
    if not rows:
        raise AppError("MALFORMED_FILE", "The ECG file is empty.", 422)
    header = [cell.strip().lower() for cell in rows[0]]
    named = {"ecg", "signal", "amplitude"}
    column = next((header.index(name) for name in named if name in header), None)
    start = 1 if column is not None else 0
    if column is None:
        candidates = [index for index in range(len(rows[0])) if all(_is_float(row[index]) for row in rows)]
        if not candidates:
            start = 1
            candidates = [index for index in range(len(rows[0])) if all(len(row) > index and _is_float(row[index]) for row in rows[1:])]
        if len(candidates) != 1:
            raise AppError("AMBIGUOUS_ECG_COLUMN", "The file must contain one identifiable ECG numeric column.", 422)
        column = candidates[0]
    values = []
    for row in rows[start:]:
        if len(row) <= column or not row[column].strip():
            raise AppError("MALFORMED_FILE", "The ECG file contains a missing or non-numeric sample.", 422)
        try:
            values.append(float(row[column]))
        except ValueError as exc:
            raise AppError("MALFORMED_FILE", "The ECG file contains a non-numeric sample.", 422) from exc
    signal = np.asarray(values, dtype=float)
    if signal.size == 0 or not np.all(np.isfinite(signal)):
        raise AppError("INVALID_SIGNAL", "The ECG file must contain finite numeric samples.", 422)
    return signal


def _is_float(value: str) -> bool:
    try:
        float(value.strip())
        return True
    except ValueError:
        return False