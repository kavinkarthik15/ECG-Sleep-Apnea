import logging
import hmac
import time

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.database import get_db
from app.ml.inference import predict_apnea_from_ecg
from app.models.persistence import VisitorSession
from app.schemas.requests import AssistantMessageRequest, ECGPredictionRequest, LongECGRequest
from app.schemas.responses import (
    AssistantMessageResponse,
    ErrorResponse,
    PredictionResponse,
    RecordingAnalysisResponse,
)
from app.services.ecg_service import analyze_ecg_recording
from app.services.file_service import parse_ecg_file
from app.services.analysis_persistence import (
    analysis_response,
    analysis_window_response,
    attach_waveform_envelopes,
    get_latest_analysis,
    get_owned_analysis,
    persist_analysis,
)
from app.services.assistant import build_analysis_context, get_assistant_provider
from app.services.visitor_sessions import (
    clear_session_cookie,
    expired_session_predicate,
    get_existing_visitor_session,
    get_existing_visitor_session_for_mutation,
    get_or_create_visitor_session,
)

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


@router.post("/session", tags=["Session"], summary="Create or resume an anonymous visitor session")
def start_session(
    visitor_session: VisitorSession = Depends(get_or_create_visitor_session),
) -> dict:
    return {"status": visitor_session.status}


@router.delete("/session", tags=["Session"], summary="End the visitor session and delete its analyses")
def end_session(
    request: Request,
    response: Response,
    visitor_session: VisitorSession = Depends(get_existing_visitor_session_for_mutation),
    db: Session = Depends(get_db),
) -> dict:
    db.delete(visitor_session)
    db.commit()
    clear_session_cookie(response, request.app.state.settings)
    return {"status": "ended"}


@router.get("/session/analysis", tags=["Analysis"], summary="Retrieve the visitor's most recent analysis")
def current_analysis(
    visitor_session: VisitorSession = Depends(get_existing_visitor_session),
    db: Session = Depends(get_db),
) -> dict:
    record = get_latest_analysis(db, visitor_session)
    if record is None:
        raise AppError("ANALYSIS_NOT_FOUND", "The requested analysis was not found.", 404)
    return analysis_response(record)


@router.get("/analyses/{analysis_ref}", tags=["Analysis"], summary="Retrieve an analysis owned by this visitor")
def get_analysis(
    analysis_ref: str,
    visitor_session: VisitorSession = Depends(get_existing_visitor_session),
    db: Session = Depends(get_db),
) -> dict:
    return analysis_response(get_owned_analysis(db, visitor_session, analysis_ref))


@router.get(
    "/analyses/{analysis_ref}/windows/{window_index}",
    tags=["Analysis"],
    summary="Retrieve waveform details for an owned analysis window",
)
def get_analysis_window(
    analysis_ref: str,
    window_index: int,
    visitor_session: VisitorSession = Depends(get_existing_visitor_session),
    db: Session = Depends(get_db),
) -> dict:
    record = get_owned_analysis(db, visitor_session, analysis_ref)
    return analysis_window_response(record, window_index)


@router.post("/assistant/message", tags=["Assistant"], summary="Answer a question about an owned ECG analysis")
def assistant_message(
    payload: AssistantMessageRequest,
    visitor_session: VisitorSession = Depends(get_existing_visitor_session_for_mutation),
    db: Session = Depends(get_db),
) -> dict:
    record = get_owned_analysis(db, visitor_session, payload.analysis_ref)
    try:
        context = build_analysis_context(
            record,
            window_index=payload.window_index,
            interval_start_sample=payload.interval_start_sample,
            interval_end_sample=payload.interval_end_sample,
            peak_sample=payload.peak_sample,
            selected_feature=payload.selected_feature,
        )
    except ValueError as exc:
        raise AppError("INVALID_ASSISTANT_CONTEXT", str(exc), 422) from exc

    reply = get_assistant_provider().answer(payload.question, context)
    return _validated_response(
        AssistantMessageResponse,
        {"status": "success", "reply": reply, "context": {
            "window_index": payload.window_index,
            "interval_start_sample": payload.interval_start_sample,
            "interval_end_sample": payload.interval_end_sample,
            "peak_sample": payload.peak_sample,
            "selected_feature": payload.selected_feature,
        }},
    )


@router.post("/predict", tags=["Prediction"], summary="Analyze one 60-second ECG window", responses={422: {"model": ErrorResponse}})
def predict(request: Request, payload: ECGPredictionRequest) -> dict:
    package = _package(request)
    if payload.sampling_rate != package.sampling_rate:
        raise AppError("INVALID_SAMPLE_RATE", "The current model expects ECG sampled at 100 Hz.", 422)
    started = time.perf_counter()
    result = predict_apnea_from_ecg(
        payload.ecg_samples,
        package,
        include_features=payload.include_features,
    )
    logger.info("endpoint=/predict duration_ms=%.1f status=success", (time.perf_counter() - started) * 1000)
    return _validated_response(PredictionResponse, result)


@router.post("/analyze-samples", tags=["Analysis"], summary="Analyze consecutive 60-second ECG windows")
def analyze_samples(
    request: Request,
    payload: LongECGRequest,
    visitor_session: VisitorSession = Depends(get_or_create_visitor_session),
    db: Session = Depends(get_db),
) -> dict:
    package = _package(request)
    result = analyze_ecg_recording(
        payload.ecg_samples,
        payload.sampling_rate,
        package,
        payload.include_features,
        include_rpeaks=True,
    )
    attach_waveform_envelopes(
        result,
        payload.ecg_samples,
        package.sampling_rate,
        package.window_seconds,
    )
    reference = persist_analysis(
        db, visitor_session, result, package.sampling_rate, package.window_seconds
    )
    record = get_owned_analysis(db, visitor_session, reference)
    return _validated_response(RecordingAnalysisResponse, analysis_response(record))


@router.post("/analyze-file", tags=["Analysis"], summary="Analyze a CSV or TXT ECG recording")
def analyze_file(
    request: Request,
    file: UploadFile = File(...),
    sampling_rate: int = Form(...),
    include_features: bool = Form(False),
    visitor_session: VisitorSession = Depends(get_or_create_visitor_session),
    db: Session = Depends(get_db),
) -> dict:
    package = _package(request)
    content = file.file.read()
    signal = parse_ecg_file(file.filename or "", content, request.app.state.settings.max_upload_mb * 1024 * 1024)
    response = analyze_ecg_recording(
        signal,
        sampling_rate,
        package,
        include_features,
        include_rpeaks=True,
    )
    attach_waveform_envelopes(
        response,
        signal,
        package.sampling_rate,
        package.window_seconds,
    )
    reference = persist_analysis(
        db, visitor_session, response, package.sampling_rate, package.window_seconds
    )
    record = get_owned_analysis(db, visitor_session, reference)
    return _validated_response(RecordingAnalysisResponse, analysis_response(record))


@router.get("/internal/cleanup", tags=["Maintenance"], summary="Delete expired visitor sessions and analyses")
def cleanup_expired_sessions(request: Request, db: Session = Depends(get_db)) -> dict:
    settings: Settings = request.app.state.settings
    configured_secret = settings.cron_secret
    if configured_secret is None:
        raise AppError("CLEANUP_NOT_CONFIGURED", "Scheduled cleanup is not configured.", 503)
    supplied = request.headers.get("authorization", "")
    expected = f"Bearer {configured_secret.get_secret_value()}"
    if not hmac.compare_digest(supplied, expected):
        raise AppError("UNAUTHORIZED", "The cleanup request is not authorized.", 401)

    result = db.execute(
        delete(VisitorSession).where(expired_session_predicate(db))
    )
    db.commit()
    return {"status": "complete", "deleted_sessions": result.rowcount}
