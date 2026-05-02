"""Normalisation and deduplication for the raw adverse_events DataFrame.

Takes the raw output of ingest.fetch_adverse_events and returns a
DataFrame aligned to the adverse_events DB schema, ready for insert.

Transformations applied (in order):
  1. Drop rows with null/empty reaction
  2. Lowercase + strip drug_name and reaction
  3. Map outcome codes → human-readable strings
  4. Parse report_date (YYYYMMDD → datetime.date; invalid → None)
  5. Cast serious to int; fill missing with 0
  6. Deduplicate by safetyreportid + reaction (most precise);
     fallback to drug_name + reaction + report_date + source
  7. Drop safetyreportid (not in DB schema)
  8. Return only schema columns
"""

import logging
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

_OUTCOME_MAP = {
    "1": "recovered",
    "2": "recovering",
    "3": "not_recovered",
    "4": "fatal",
    "5": "unknown",
    "6": "unknown",
}

_SCHEMA_COLUMNS = ["drug_name", "reaction", "outcome", "report_date", "serious", "source"]


def clean_adverse_events(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise and deduplicate raw adverse events DataFrame.

    Args:
        df: Raw DataFrame from ingest.fetch_adverse_events.
            Expected columns: safetyreportid, drug_name, reaction,
            outcome, report_date, serious, source

    Returns:
        Cleaned DataFrame with columns matching adverse_events schema.
        May be empty if all rows were dropped.
    """
    if df.empty:
        logger.warning("clean_adverse_events received empty DataFrame")
        return pd.DataFrame(columns=_SCHEMA_COLUMNS)

    original_count = len(df)
    df = df.copy()

    # 1. Drop rows with null or empty reaction
    df = df[df["reaction"].notna() & (df["reaction"].str.strip() != "")]
    _log_drop("null/empty reaction", original_count, len(df))

    if df.empty:
        return pd.DataFrame(columns=_SCHEMA_COLUMNS)

    # 2. Lowercase + strip text fields
    df["drug_name"] = df["drug_name"].str.lower().str.strip()
    df["reaction"] = df["reaction"].str.lower().str.strip()

    # 3. Map outcome codes to human-readable strings
    df["outcome"] = df["outcome"].astype(str).map(_OUTCOME_MAP).fillna("unknown")

    # 4. Parse report_date: YYYYMMDD string → datetime.date
    df["report_date"] = df["report_date"].apply(_parse_date)

    # 5. Coerce serious to int; fill missing with 0
    df["serious"] = pd.to_numeric(df["serious"], errors="coerce").fillna(0).astype(int)

    # 6. Deduplicate
    before_dedup = len(df)
    if "safetyreportid" in df.columns and df["safetyreportid"].notna().any():
        df = df.drop_duplicates(subset=["safetyreportid", "reaction"])
    else:
        df = df.drop_duplicates(subset=["drug_name", "reaction", "report_date", "source"])
    _log_drop("duplicates", before_dedup, len(df))

    # 7. Drop safetyreportid — not in DB schema
    if "safetyreportid" in df.columns:
        df = df.drop(columns=["safetyreportid"])

    # 8. Return only schema columns (in order)
    df = df[_SCHEMA_COLUMNS].reset_index(drop=True)

    logger.info("clean_adverse_events: %d → %d rows", original_count, len(df))
    return df


def _parse_date(value) -> date | None:
    """Parse YYYYMMDD string to datetime.date. Returns None on failure."""
    if pd.isna(value) or str(value).strip() == "":
        return None
    try:
        s = str(value).strip()
        return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except (ValueError, IndexError):
        return None


def _log_drop(reason: str, before: int, after: int) -> None:
    dropped = before - after
    if dropped > 0:
        logger.debug("Dropped %d rows (%s)", dropped, reason)
