from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
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

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
