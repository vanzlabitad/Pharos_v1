"""SQLite interface for Pharos using SQLAlchemy Core.

All functions accept an Engine as the first argument — callers control
the connection lifecycle; there is no hidden global state.
"""

import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"

# Explicit column list so callers can pass DataFrames with extra columns
# (e.g. chi_squared from compute_all_signals) without breaking the insert.
_SIGNAL_SCORE_COLS = [
    "drug_name", "reaction", "ror", "ror_lower", "ror_upper",
    "prr", "n_reports", "computed_date",
]


def get_engine(db_path: str | Path | None = None) -> Engine:
    """Return a SQLAlchemy engine for the given SQLite path.

    If db_path is None, falls back to the DB_PATH env var, then to db/pharos.db.
    Creates the parent directory if it doesn't exist.
    """
    import os

    if db_path is None:
        db_path = os.getenv("DB_PATH", "db/pharos.db")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return create_engine(f"sqlite:///{db_path}")


def create_tables(engine: Engine) -> None:
    """Execute schema.sql against the database. Idempotent (IF NOT EXISTS).

    Uses the underlying sqlite3 executescript() so comments and multi-statement
    files are handled correctly without manual semicolon splitting.
    """
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with engine.connect() as conn:
        # executescript() handles multi-statement SQL files natively and
        # commits automatically — do not call conn.commit() after this.
        conn.connection.executescript(sql)
    logger.info("Tables created (or already exist)")


def insert_adverse_events(engine: Engine, df: pd.DataFrame) -> int:
    """Bulk-insert a cleaned adverse_events DataFrame. Returns row count inserted."""
    if df.empty:
        logger.warning("insert_adverse_events called with empty DataFrame — skipping")
        return 0

    expected = {"drug_name", "reaction", "outcome", "report_date", "serious", "source"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")

    with engine.connect() as conn:
        df.to_sql("adverse_events", conn, if_exists="append", index=False)
        conn.commit()

    logger.info("Inserted %d rows into adverse_events", len(df))
    return len(df)


def insert_signal_scores(engine: Engine, df: pd.DataFrame) -> int:
    """Bulk-insert a signal_scores DataFrame. Returns row count inserted."""
    if df.empty:
        logger.warning("insert_signal_scores called with empty DataFrame — skipping")
        return 0

    expected = {"drug_name", "reaction", "ror", "ror_lower", "ror_upper", "prr", "n_reports", "computed_date"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")

    with engine.connect() as conn:
        df[_SIGNAL_SCORE_COLS].to_sql("signal_scores", conn, if_exists="append", index=False)
        conn.commit()

    logger.info("Inserted %d rows into signal_scores", len(df))
    return len(df)


def clear_adverse_events(engine: Engine) -> None:
    """Delete all rows from adverse_events. Used before a full re-ingest."""
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM adverse_events"))
        conn.commit()
    logger.info("Cleared adverse_events")


def clear_signal_scores(engine: Engine) -> None:
    """Delete all rows from signal_scores. Used before recomputing signals."""
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM signal_scores"))
        conn.commit()
    logger.info("Cleared signal_scores")
