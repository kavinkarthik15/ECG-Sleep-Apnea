import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.ml.model_loader import ModelPackage, load_model_package


def create_app(package: ModelPackage | None = None, settings: Settings | None = None, load_artifact: bool = True) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if package is not None:
            application.state.model_package = package
        elif load_artifact:
            application.state.model_package = load_model_package(active_settings.model_path)
        logging.getLogger(__name__).info("application_started model_loaded=%s", hasattr(application.state, "model_package"))
        yield

    application = FastAPI(title="ECG Sleep Apnea Screening API", version="1.0.0", description="Academic ECG-based screening research prototype. This service does not provide a medical diagnosis.", lifespan=lifespan)
    application.state.settings = active_settings
    application.add_middleware(CORSMiddleware, allow_origins=active_settings.cors_origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"])
    application.include_router(router)

    @application.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"status": "error", "code": exc.code, "message": exc.message})

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"status": "error", "code": "VALIDATION_ERROR", "message": "The request is invalid."})

    @application.get("/", tags=["System"], summary="Basic API information")
    def root() -> dict[str, str]:
        return {"name": "ECG Sleep Apnea Screening API", "status": "available", "disclaimer": "Academic screening prototype; not a medical diagnosis."}

    @application.get("/health", tags=["System"], summary="Check API and model health")
    def health(request: Request) -> dict[str, Any]:
        package = getattr(request.app.state, "model_package", None)
        return {"status": "healthy" if package is not None else "degraded", "model_loaded": package is not None, "model_version": package.model_version if package else None}

    return application


app = create_app()