"""Alembic environment for IntentGuard migrations.

Resolution order for the target database:
1. ``INTENTGUARD_MIGRATION_DB`` (explicit override, used by tests)
2. ``INTENTGUARD_DATABASE_URL`` (PostgreSQL deployments)
3. ``INTENTGUARD_SQLITE_PATH``-based SQLite URL (default)
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# make the intentguard package importable when invoked from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intentguard.storage.sql import meta  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = meta


def _database_url() -> str:
    explicit = os.environ.get("INTENTGUARD_MIGRATION_DB")
    if explicit:
        return explicit
    postgres = os.environ.get("INTENTGUARD_DATABASE_URL")
    if postgres:
        return postgres
    sqlite_path = os.environ.get("INTENTGUARD_SQLITE_PATH", "./data/intentguard.db")
    path = Path(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-friendly ALTERs
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
