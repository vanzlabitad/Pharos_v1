"""Static JSON export functions for the Pharos dashboard.

Exports DB tables to records-oriented JSON files consumed by the Next.js
frontend. Called by run_refresh.py as part of the weekly pipeline.

Output format: [{...}, {...}, ...] (orient="records") so the frontend can
iterate directly without any envelope unwrapping.
"""

import json
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.normalise import canonical

logger = logging.getLogger(__name__)


def export_signals_json(engine: Engine, output_path: str | Path) -> int:
    """Export signal_scores table to a records-oriented JSON file.

    Args:
        engine:      SQLAlchemy engine pointing at pharos.db.
        output_path: Destination file path (created if absent).

    Returns:
        Number of rows written. 0 if signal_scores is empty (file still
        written as an empty array so the frontend doesn't 404).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with engine.connect() as conn:
        df = pd.read_sql(text("SELECT * FROM signal_scores"), conn)

    if df.empty:
        logger.warning("signal_scores is empty — writing empty JSON array")
        output_path.write_text("[]", encoding="utf-8")
        return 0

    df["flagged"] = (
        (df["ror_lower"] > 1.0)
        & (df["prr"] >= 2.0)
        & (df["n_reports"] >= 3)
        & (df["chi_squared"] >= 4.0)
    )

    df.to_json(output_path, orient="records", indent=2, date_format="iso")
    logger.info("Exported %d signal rows to %s", len(df), output_path)
    return len(df)


def export_adverse_events_json(
    engine: Engine, drug_name: str, output_path: str | Path
) -> int:
    """Export adverse events for one drug to a records-oriented JSON file.

    Args:
        engine:      SQLAlchemy engine pointing at pharos.db.
        drug_name:   Drug to filter by (must match the normalised lowercase
                     value stored in the DB).
        output_path: Destination file path (created if absent).

    Returns:
        Number of rows written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT * FROM adverse_events WHERE drug_name = :drug"),
            conn,
            params={"drug": canonical(drug_name)},
        )

    if df.empty:
        logger.warning("No adverse events found for '%s' — writing empty array", drug_name)
        output_path.write_text("[]", encoding="utf-8")
        return 0

    df.to_json(output_path, orient="records", indent=2, date_format="iso")
    logger.info(
        "Exported %d adverse event rows for '%s' to %s",
        len(df), drug_name, output_path,
    )
    return len(df)
