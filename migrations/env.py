from logging.config import fileConfig

from alembic import context

from app.core.config import get_settings
from app.database import Base, create_database_engine
from app.models.persistence import ECGAnalysis, VisitorSession

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
settings = get_settings()


def run_migrations_offline() -> None:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL must be configured before running migrations.")
    engine = create_database_engine(settings)
    if engine is None:
        raise RuntimeError("DATABASE_URL must be configured before running migrations.")
    try:
        context.configure(
            url=engine.url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    finally:
        engine.dispose()


def run_migrations_online() -> None:
    engine = create_database_engine(settings)
    if engine is None:
        raise RuntimeError("DATABASE_URL must be configured before running migrations.")
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
