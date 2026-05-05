"""SQLite interface for Pharos using SQLAlchemy Core.

All functions accept an Engine as the first argument — callers control
the connection lifecycle; there is no hidden global state.
"""

import json
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

load_dotenv()

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"
_ALIASES_PATH = Path(__file__).parent / "drug_aliases.json"

_SIGNAL_SCORE_COLS = [
    "drug_name", "reaction", "ror", "ror_lower", "ror_upper",
    "prr", "chi_squared", "n_reports", "computed_date",
]


def get_engine(db_path: str | Path | None = None) -> Engine:
    """Return a SQLAlchemy engine for the given SQLite path.

    If db_path is None, falls back to the DB_PATH env var, then to db/pharos.db.
    Creates the parent directory if it doesn't exist. Also installs a
    connect-time hook that runs ``PRAGMA foreign_keys = ON`` on every new
    connection — SQLite ignores FK constraints otherwise.
    """
    import os

    if db_path is None:
        db_path = os.getenv("DB_PATH", "db/pharos.db")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _conn_record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


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
    """Bulk-insert a cleaned adverse_events DataFrame. Returns row count inserted.

    Ensures every distinct ``drug_name`` exists in ``drugs(name)`` first so
    that the FK constraint on adverse_events.drug_name is satisfied.
    """
    if df.empty:
        logger.warning("insert_adverse_events called with empty DataFrame — skipping")
        return 0

    expected = {"drug_name", "reaction", "outcome", "report_date", "serious", "source"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")

    distinct_drugs = sorted(set(df["drug_name"].dropna().unique()))
    with engine.connect() as conn:
        for name in distinct_drugs:
            conn.execute(
                text("INSERT OR IGNORE INTO drugs (name) VALUES (:name)"),
                {"name": name},
            )
        df.to_sql("adverse_events", conn, if_exists="append", index=False)
        conn.commit()

    logger.info(
        "Inserted %d rows into adverse_events (across %d drug names)",
        len(df), len(distinct_drugs),
    )
    return len(df)


def insert_signal_scores(engine: Engine, df: pd.DataFrame) -> int:
    """Bulk-insert a signal_scores DataFrame. Returns row count inserted."""
    if df.empty:
        logger.warning("insert_signal_scores called with empty DataFrame — skipping")
        return 0

    expected = set(_SIGNAL_SCORE_COLS)
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")

    with engine.connect() as conn:
        df[_SIGNAL_SCORE_COLS].to_sql("signal_scores", conn, if_exists="append", index=False)
        conn.commit()

    logger.info("Inserted %d rows into signal_scores", len(df))
    return len(df)


def seed_drug_aliases(engine: Engine) -> int:
    """Seed the drug_aliases table from pipeline/drug_aliases.json.

    Idempotent: uses INSERT OR REPLACE so re-running picks up edits to the
    JSON file. Each canonical_name is also upserted into ``drugs`` to keep
    the FK from drug_aliases satisfied.
    """
    if not _ALIASES_PATH.exists():
        logger.warning("Alias file %s missing — skipping seed", _ALIASES_PATH)
        return 0

    with _ALIASES_PATH.open(encoding="utf-8") as f:
        raw: dict[str, str] = json.load(f)

    pairs = [
        (alias.lower().strip(), canonical.lower().strip())
        for alias, canonical in raw.items()
    ]
    canonical_names = sorted({c for _, c in pairs})

    with engine.connect() as conn:
        for name in canonical_names:
            conn.execute(
                text("INSERT OR IGNORE INTO drugs (name) VALUES (:name)"),
                {"name": name},
            )
        for alias, canonical in pairs:
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO drug_aliases (alias, canonical_name) "
                    "VALUES (:alias, :canonical)"
                ),
                {"alias": alias, "canonical": canonical},
            )
        conn.commit()

    logger.info(
        "Seeded %d alias rows across %d canonical drugs", len(pairs), len(canonical_names),
    )
    return len(pairs)


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
