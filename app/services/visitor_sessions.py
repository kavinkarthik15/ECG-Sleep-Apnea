import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request, Response
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.database import get_db
from app.models.persistence import VisitorSession

INACTIVITY_TIMEOUT = timedelta(hours=2)
ABSOLUTE_LIFETIME = timedelta(hours=12)


def _session_cookie_options(settings: Settings) -> dict[str, object]:
    return {
        "key": settings.session_cookie_name,
        "path": "/",
        "secure": settings.session_cookie_secure,
        "httponly": True,
        "samesite": settings.session_cookie_samesite,
    }


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        **_session_cookie_options(settings),
        value=token,
        max_age=int(ABSOLUTE_LIFETIME.total_seconds()),
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(**_session_cookie_options(settings))


def require_allowed_origin(request: Request, *, required: bool = False) -> None:
    settings: Settings = request.app.state.settings
    origin = request.headers.get("origin")
    if origin is not None:
        allowed = {item.rstrip("/") for item in settings.cors_origins}
        if origin.rstrip("/") not in allowed:
            raise AppError("CSRF_VALIDATION_FAILED", "The request origin is not allowed.", 403)
        return
    if required and settings.session_cookie_name in request.cookies:
        raise AppError("CSRF_VALIDATION_FAILED", "An Origin header is required for this request.", 403)


def _get_visitor_session(
    request: Request,
    response: Response,
    db: Session,
    *,
    create_if_missing: bool,
) -> VisitorSession:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if token is None:
        if not create_if_missing:
            raise AppError("VISITOR_SESSION_REQUIRED", "A valid visitor session is required.", 401)
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        visitor_session = VisitorSession(
            session_id_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            created_at=now,
            last_activity_at=now,
            expires_at=now + ABSOLUTE_LIFETIME,
            status="active",
        )
        db.add(visitor_session)
        db.commit()
        set_session_cookie(response, token, settings)
        return visitor_session

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    visitor_session = db.scalar(
        select(VisitorSession).where(VisitorSession.session_id_hash == token_hash)
    )
    if visitor_session is None:
        request.state.clear_visitor_session_cookie = True
        raise AppError("VISITOR_SESSION_INVALID", "The visitor session is invalid or expired.", 401)

    active_expiry, active_inactivity, database_now = _session_expiry_predicates(db)
    touched = db.execute(
        update(VisitorSession)
        .where(
            VisitorSession.id == visitor_session.id,
            VisitorSession.status == "active",
            active_expiry,
            active_inactivity,
        )
        .values(last_activity_at=database_now)
        .execution_options(synchronize_session=False)
    )
    if touched.rowcount != 1:
        db.execute(delete(VisitorSession).where(VisitorSession.id == visitor_session.id))
        db.commit()
        request.state.clear_visitor_session_cookie = True
        raise AppError("VISITOR_SESSION_EXPIRED", "The visitor session is invalid or expired.", 401)

    db.commit()
    return visitor_session


def get_or_create_visitor_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> VisitorSession:
    require_allowed_origin(
        request,
        required=settings_cookie_present(request),
    )
    return _get_visitor_session(request, response, db, create_if_missing=True)


def get_existing_visitor_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> VisitorSession:
    require_allowed_origin(request)
    return _get_visitor_session(request, response, db, create_if_missing=False)


def get_existing_visitor_session_for_mutation(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> VisitorSession:
    require_allowed_origin(request, required=True)
    return _get_visitor_session(request, response, db, create_if_missing=False)


def settings_cookie_present(request: Request) -> bool:
    settings: Settings = request.app.state.settings
    return settings.session_cookie_name in request.cookies


def _session_expiry_predicates(db: Session):
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        database_now = func.clock_timestamp()
        return (
            VisitorSession.expires_at > database_now,
            VisitorSession.last_activity_at
            > database_now - INACTIVITY_TIMEOUT,
            database_now,
        )
    if dialect == "sqlite":
        database_now = func.strftime("%Y-%m-%d %H:%M:%f", "now")
        return (
            func.julianday(VisitorSession.expires_at) > func.julianday("now"),
            func.julianday(VisitorSession.last_activity_at)
            > func.julianday("now", "-7200 seconds"),
            database_now,
        )
    raise RuntimeError(f"Unsupported session database dialect: {dialect}")


def expired_session_predicate(db: Session):
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        database_now = func.clock_timestamp()
        inactivity_expiry = VisitorSession.last_activity_at <= (
            database_now
            - text(f"INTERVAL '{int(INACTIVITY_TIMEOUT.total_seconds())} seconds'")
        )
        absolute_expiry = VisitorSession.expires_at <= database_now
    elif dialect == "sqlite":
        inactivity_expiry = (
            func.julianday(VisitorSession.last_activity_at)
            <= func.julianday("now", "-7200 seconds")
        )
        absolute_expiry = (
            func.julianday(VisitorSession.expires_at) <= func.julianday("now")
        )
    else:
        raise RuntimeError(f"Unsupported session database dialect: {dialect}")

    return or_(
        VisitorSession.status != "active",
        absolute_expiry,
        inactivity_expiry,
    )
