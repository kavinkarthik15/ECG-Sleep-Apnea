from collections.abc import Generator

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.doh_resolver import DohResolutionError, DohResolver


def _create_doh_connection(url, resolver: DohResolver):
    import psycopg

    hostname = url.host
    if not hostname:
        raise ValueError("DATABASE_URL must include a hostname for DNS-over-HTTPS resolution.")
    addresses = resolver.resolve(hostname)
    last_error = None
    conninfo = url.set(drivername="postgresql").render_as_string(hide_password=False)
    for address in addresses:
        try:
            return psycopg.connect(conninfo, hostaddr=address)
        except psycopg.Error as exc:
            last_error = exc
    raise last_error or DohResolutionError("DNS-over-HTTPS returned no usable address.")


class Base(DeclarativeBase):
    pass


def create_database_engine(settings: Settings) -> Engine | None:
    if settings.database_url is None:
        return None

    url = make_url(settings.database_url.get_secret_value())
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername.startswith("sqlite"):
        if settings.app_env.lower() != "test":
            raise ValueError("SQLite is supported only by the isolated test configuration.")
    elif url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL must use PostgreSQL with psycopg.")

    connect_args = {"check_same_thread": False} if url.drivername.startswith("sqlite") else {}
    poolclass = NullPool
    if url.drivername.startswith("sqlite") and url.database in {None, "", ":memory:"}:
        poolclass = StaticPool

    engine_kwargs = {
        "connect_args": connect_args,
        "poolclass": poolclass,
        "pool_pre_ping": True,
    }
    if settings.database_dns_over_https and url.drivername == "postgresql+psycopg":
        resolver = DohResolver(timeout_seconds=settings.database_dns_over_https_timeout_seconds)
        engine_kwargs["creator"] = lambda: _create_doh_connection(url, resolver)

    engine = create_engine(url, **engine_kwargs)
    if url.drivername.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise AppError("DATABASE_UNAVAILABLE", "Persistent storage is not configured.", 503)
    db = factory()
    try:
        yield db
    finally:
        db.close()
