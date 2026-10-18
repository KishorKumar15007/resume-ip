from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from app.database import Base, settings
from app.models import User, JobPosting, Submission

config = context.config


def get_migration_database_url() -> str:
    if settings.migration_database_url:
        return settings.migration_database_url

    runtime_url = make_url(settings.database_url)
    if runtime_url.get_backend_name() == "postgresql" and runtime_url.host in {
        "127.0.0.1",
        "localhost",
        "postgres",
    }:
        return settings.database_url

    raise RuntimeError(
        "MIGRATION_DATABASE_URL is required for non-local database migrations."
    )


migration_database_url = get_migration_database_url()
config.set_main_option("sqlalchemy.url", migration_database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
