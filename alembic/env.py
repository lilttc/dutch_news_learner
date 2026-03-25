"""
Alembic environment.

DATABASE_URL must point at the target database (same as the app). For existing
deployments that already match SQLAlchemy models via _migrate_schema(), stamp
this revision without running DDL::

    alembic stamp baseline_001

New environments can also rely on app startup _migrate_schema until you move
DDL fully into Alembic revisions.
"""

from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import create_engine, pool

from src.models.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///data/dutch_news.db")


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
