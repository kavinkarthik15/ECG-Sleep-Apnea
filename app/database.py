from collections.abc import Generator

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import Settings
from app.core.exceptions import AppError


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

    engine = create_engine(
        url,
        connect_args=connect_args,
        poolclass=poolclass,
        pool_pre_ping=True,
    )
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
