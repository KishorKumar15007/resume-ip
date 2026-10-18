from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


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
        env_file = Path(__file__).resolve().parents[3] / ".env",
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
