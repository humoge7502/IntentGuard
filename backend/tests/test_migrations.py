"""Alembic migration tests: upgrade head on a fresh database produces the
full schema; downgrade base reverses it; re-upgrade is idempotent."""

from pathlib import Path

import sqlalchemy
from alembic.config import Config

from alembic import command
from intentguard.storage.sql import meta

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _config_for(db_path: Path) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("path_separator", "os")
    import os

    os.environ["INTENTGUARD_MIGRATION_DB"] = f"sqlite:///{db_path}"
    return cfg


def test_migration_upgrade_downgrade_upgrade(tmp_path):
    db_path = tmp_path / "mig.db"
    cfg = _config_for(db_path)

    command.upgrade(cfg, "head")

    engine = sqlalchemy.create_engine(f"sqlite:///{db_path}")
    inspector = sqlalchemy.inspect(engine)
    migrated_tables = set(inspector.get_table_names())
    expected_tables = {t.name for t in meta.sorted_tables} | {"alembic_version"}
    missing = expected_tables - migrated_tables
    assert not missing, f"migration missing tables: {missing}"

    # columns sanity on the security-critical tables
    decision_cols = {c["name"] for c in inspector.get_columns("decisions")}
    assert {"decision_id", "org_id", "action_digest", "decision", "risk_json"} <= decision_cols
    audit_cols = {c["name"] for c in inspector.get_columns("audit_events")}
    assert {"seq", "org_id", "prev_hash", "hash"} <= audit_cols

    # downgrade base reverses everything, then re-upgrade is idempotent
    command.downgrade(cfg, "base")
    inspector = sqlalchemy.inspect(engine)
    assert not (set(inspector.get_table_names()) & set(t.name for t in meta.sorted_tables))
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")  # idempotent no-op
    engine.dispose()

    import os

    os.environ.pop("INTENTGUARD_MIGRATION_DB", None)
