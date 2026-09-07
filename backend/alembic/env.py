"""
Alembic environment.

Design decision: Alembic reads the database URL and the metadata target
from our own app config/models instead of duplicating them in alembic.ini.

Why: a single source of truth for the DB connection string and for the
set of tables that should exist. If Sprint 1 adds a new model imported
into app.db.session.Base's metadata, `alembic revision --autogenerate`
picks it up automatically with no changes here.

Note: Alembic runs synchronously, so we use the sync (psycopg2) URL even
though the running application uses the async (asyncpg) URL.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.session import Base

# Sprint 1+ will import model modules here so their tables are registered
# on Base.metadata before autogenerate runs, e.g.:
#   from app.models import patient, doctor, clinic  # noqa: F401

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

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
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
