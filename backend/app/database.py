from pathlib import Path
import logging
import os
from contextvars import ContextVar
from threading import Lock
from time import perf_counter

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


_MODULE_PARENTS = Path(__file__).resolve().parents
# Local development retains the owner-managed external dotenv path.  The
# container image has fewer path parents, so Compose supplies its settings
# through process environment variables instead of attempting this lookup.
_HOST_ENV_FILE = (
    _MODULE_PARENTS[3] / ".env" if len(_MODULE_PARENTS) > 3 else None
)


class Settings(BaseSettings):
    database_url: str
    migration_database_url: str | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 5
    gcs_bucket_name: str
    gcp_project_id: str
    pubsub_resume_uploaded_topic: str
    cors_allowed_origins: str = ""

    model_config = SettingsConfigDict(
        env_file = _HOST_ENV_FILE,
        extra="ignore",
    )


settings = Settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)

# Diagnostic events contain only timings, counts, and random request IDs.
# Enable explicitly for a bounded investigation; never log SQL or parameters.
db_trace_request: ContextVar[str] = ContextVar("db_trace_request", default="-")
_trace_enabled = os.getenv("DB_LIFECYCLE_TRACE") == "1"
_trace_logger = logging.getLogger("resume_ip.db_lifecycle")
_trace_lock = Lock()
_trace_checked_out = 0


def _trace_event(name: str, **fields: object) -> None:
    if _trace_enabled:
        _trace_logger.warning(
            "db_lifecycle %s request=%s %s",
            name,
            db_trace_request.get(),
            " ".join(f"{key}={value}" for key, value in fields.items()),
        )


if _trace_enabled:
    @event.listens_for(engine, "checkout")
    def _trace_checkout(dbapi_connection, connection_record, connection_proxy):
        global _trace_checked_out
        with _trace_lock:
            _trace_checked_out += 1
            count = _trace_checked_out
        connection_record.info["trace_checkout_at"] = perf_counter()
        _trace_event("checkout", checked_out=count)

    @event.listens_for(engine, "checkin")
    def _trace_checkin(dbapi_connection, connection_record):
        global _trace_checked_out
        started = connection_record.info.pop("trace_checkout_at", None)
        with _trace_lock:
            _trace_checked_out -= 1
            count = _trace_checked_out
        held_ms = round((perf_counter() - started) * 1000, 3) if started else None
        _trace_event("checkin", checked_out=count, held_ms=held_ms)

    @event.listens_for(engine, "before_cursor_execute")
    def _trace_sql_begin(conn, cursor, statement, parameters, context, executemany):
        conn.info["trace_sql_at"] = perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _trace_sql_end(conn, cursor, statement, parameters, context, executemany):
        started = conn.info.pop("trace_sql_at", None)
        if started:
            _trace_event("sql_complete", duration_ms=round((perf_counter() - started) * 1000, 3))

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    _trace_event("session_created")
    try:
        _trace_event("session_yield")
        yield db
    finally:
        _trace_event("session_close_begin")
        db.close()
        _trace_event("session_close_end")
