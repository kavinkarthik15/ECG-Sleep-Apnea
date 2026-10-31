import logging
import time

from fastapi import APIRouter, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import AppError, MathematicalExplanationError
from app.ml.features import FEATURE_NAMES
from app.ml.inference import predict_apnea_from_ecg
from app.schemas.requests import ECGPredictionRequest, LongECGRequest
from app.schemas.responses import (
    AIExplanationStatus,
    ErrorResponse,
    PredictionResponse,
    RecordingAnalysisResponse,
)
from app.services.ai_explanation_service import (
    build_window_context,
    safe_generate_ai_explanation,
)
from app.services.ecg_service import analyze_ecg_recording
from app.services.file_service import parse_ecg_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _package(request: Request):
    package = getattr(request.app.state, "model_package", None)
    if package is None:
        raise AppError("MODEL_UNAVAILABLE", "The inference model is unavailable.", 503)
    return package


def _validated_response(response_model, response: dict) -> dict:
    return response_model.model_validate(response).model_dump(exclude_unset=True)


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
    mathematical_explanation_unavailable = False
    try:
        result = predict_apnea_from_ecg(
            payload.ecg_samples,
            package,
            include_features=payload.include_features,
            include_explanation=payload.include_explanation or payload.include_ai_explanation,
        )
    except MathematicalExplanationError:
        if not payload.include_ai_explanation:
            raise
        mathematical_explanation_unavailable = True
        result = predict_apnea_from_ecg(
            payload.ecg_samples,
            package,
            include_features=payload.include_features,
            include_explanation=False,
        )
    if payload.include_ai_explanation:
        if mathematical_explanation_unavailable or "explanation" not in result:
            ai_explanation = None
            ai_status = AIExplanationStatus(status="unavailable", code="mathematical_explanation_unavailable")
        else:
            context = build_window_context(
                package.model_version,
                result["result"],
                result["explanation"],
                result["window"],
                result["signal_quality"],
            )
            ai_explanation, ai_status = safe_generate_ai_explanation(
                context,
                request.app.state.settings,
            )
        result["ai_explanation"] = ai_explanation.model_dump() if ai_explanation else None
        result["ai_explanation_status"] = ai_status.model_dump()
    if not payload.include_explanation:
        result.pop("explanation", None)
    logger.info("endpoint=/predict duration_ms=%.1f status=success", (time.perf_counter() - started) * 1000)
    return _validated_response(PredictionResponse, result)


@router.post("/analyze-samples", tags=["Analysis"], summary="Analyze consecutive 60-second ECG windows")
def analyze_samples(request: Request, payload: LongECGRequest) -> dict:
    package = _package(request)
    return _validated_response(
        RecordingAnalysisResponse,
        analyze_ecg_recording(
            payload.ecg_samples,
            payload.sampling_rate,
            package,
            payload.include_features,
            payload.include_explanation,
            include_ai_explanation=payload.include_ai_explanation,
            settings=request.app.state.settings,
        ),
    )


@router.post("/analyze-file", tags=["Analysis"], summary="Analyze a CSV or TXT ECG recording")
async def analyze_file(
    request: Request,
    file: UploadFile = File(...),
    sampling_rate: int = Form(...),
    include_features: bool = Form(False),
    include_explanation: bool = Form(False),
    include_ai_explanation: bool = Form(False),
) -> dict:
    package = _package(request)
    content = await file.read()
    signal = parse_ecg_file(file.filename or "", content, request.app.state.settings.max_upload_mb * 1024 * 1024)
    response = await run_in_threadpool(
        analyze_ecg_recording,
        signal,
        sampling_rate,
        package,
        include_features,
        include_explanation,
        include_ai_explanation=include_ai_explanation,
        settings=request.app.state.settings,
    )
    return _validated_response(RecordingAnalysisResponse, response)
