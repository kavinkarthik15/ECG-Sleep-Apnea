import logging
import time

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.core.exceptions import AppError
from app.ml.features import FEATURE_NAMES
from app.ml.inference import predict_apnea_from_ecg
from app.schemas.requests import ECGPredictionRequest, LongECGRequest
from app.schemas.responses import ErrorResponse
from app.services.ecg_service import analyze_ecg_recording
from app.services.file_service import parse_ecg_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _package(request: Request):
    package = getattr(request.app.state, "model_package", None)
    if package is None:
        raise AppError("MODEL_UNAVAILABLE", "The inference model is unavailable.", 503)
    return package


@router.get("/model-info", tags=["Model"], summary="Return non-sensitive model metadata")
def model_info(request: Request) -> dict:
    package = _package(request)
    return {"model_version": package.model_version, "sampling_rate": package.sampling_rate, "window_seconds": package.window_seconds, "required_samples": package.sampling_rate * package.window_seconds, "feature_count": len(package.feature_names), "threshold": package.threshold, "supported_file_types": [".csv", ".txt"]}


@router.post("/predict", tags=["Prediction"], summary="Analyze one 60-second ECG window", responses={422: {"model": ErrorResponse}})
def predict(request: Request, payload: ECGPredictionRequest) -> dict:
    package = _package(request)
    if payload.sampling_rate != package.sampling_rate:
        raise AppError("INVALID_SAMPLE_RATE", "The current model expects ECG sampled at 100 Hz.", 422)
    started = time.perf_counter()
    result = predict_apnea_from_ecg(payload.ecg_samples, package, payload.include_features)
    logger.info("endpoint=/predict duration_ms=%.1f status=success", (time.perf_counter() - started) * 1000)
    return result


@router.post("/analyze-samples", tags=["Analysis"], summary="Analyze consecutive 60-second ECG windows")
def analyze_samples(request: Request, payload: LongECGRequest) -> dict:
    package = _package(request)
    return analyze_ecg_recording(payload.ecg_samples, payload.sampling_rate, package, payload.include_features)


@router.post("/analyze-file", tags=["Analysis"], summary="Analyze a CSV or TXT ECG recording")
async def analyze_file(request: Request, file: UploadFile = File(...), sampling_rate: int = Form(...), include_features: bool = Form(False)) -> dict:
    package = _package(request)
    content = await file.read()
    signal = parse_ecg_file(file.filename or "", content, request.app.state.settings.max_upload_mb * 1024 * 1024)
    return analyze_ecg_recording(signal, sampling_rate, package, include_features)