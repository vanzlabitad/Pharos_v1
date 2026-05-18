"""Weekly data refresh orchestration script.

Intended to be called by .github/workflows/refresh.yml on a weekly schedule,
but can also be run locally to seed or update the database.

What it does (in order):
  1. Create tables (idempotent)
  2. For each drug in DRUG_LIST:
       a. Fetch adverse events from OpenFDA
       b. Clean and insert into adverse_events
  3. Compute ROR/PRR signals across the full adverse_events table
  4. Replace signal_scores with the freshly computed signals
  5. Export signals JSON + per-drug adverse event JSON to OUTPUT_DIR

Usage:
    python pipeline/run_refresh.py

Environment:
    OPENFDA_API_KEY  — OpenFDA API key (from .env or environment)
    DB_PATH          — SQLite path (default: db/pharos.db)
"""

import logging
import sys
from pathlib import Path

# Allow `python pipeline/run_refresh.py` from the project root by ensuring
# the project root is on sys.path regardless of invocation style.
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.db import (
    get_engine,
    create_tables,
    insert_adverse_events,
    insert_signal_scores,
    clear_adverse_events,
    clear_signal_scores,
    seed_drug_aliases,
)
from pipeline.ingest import fetch_adverse_events
from pipeline.clean import clean_adverse_events
from pipeline.export import export_signals_json, export_adverse_events_json
from pipeline.summarize import generate_summaries, export_summaries_json
from analysis.disproportionality import compute_all_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

DRUG_LIST = ["ibuprofen", "aspirin", "metformin"]
MAX_RECORDS_PER_DRUG = 10_000
OUTPUT_DIR = Path("dashboard/public/data")


def main() -> int:
    """Run the full refresh pipeline. Returns exit code (0 = success)."""
    engine = get_engine()
    create_tables(engine)
    seed_drug_aliases(engine)

    # ── Step 1: Re-ingest all drugs ──────────────────────────────────────────
    logger.info("Clearing adverse_events for fresh ingest")
    clear_adverse_events(engine)

    ingested: dict[str, int] = {}
    failed: list[str] = []

    for drug in DRUG_LIST:
        logger.info("Ingesting '%s' (max %d records)...", drug, MAX_RECORDS_PER_DRUG)
        raw = fetch_adverse_events(drug, max_records=MAX_RECORDS_PER_DRUG)
        if raw.empty:
            logger.warning("No data returned for '%s' — skipping", drug)
            failed.append(drug)
            continue

        clean = clean_adverse_events(raw)
        if clean.empty:
            logger.warning("All rows dropped after cleaning for '%s' — skipping", drug)
            failed.append(drug)
            continue

        n = insert_adverse_events(engine, clean)
        ingested[drug] = n

    if not ingested:
        logger.error("No drugs were successfully ingested — aborting")
        return 1

    logger.info(
        "Ingestion complete: %s",
        ", ".join(f"{d}={n}" for d, n in ingested.items()),
    )
    if failed:
        logger.warning("Failed drugs (no data or all rows dropped): %s", failed)

    # ── Step 2: Recompute signals ────────────────────────────────────────────
    logger.info("Computing ROR/PRR signals...")
    signals = compute_all_signals(engine)

    if signals.empty:
        logger.warning("No signals computed — signal_scores will be empty")
    else:
        clear_signal_scores(engine)
        insert_signal_scores(engine, signals)

    # ── Step 3: Export static JSON ───────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    n_sig = export_signals_json(engine, OUTPUT_DIR / "signals.json")
    logger.info("Exported signals.json (%d rows)", n_sig)

    for drug in ingested:
        n_ae = export_adverse_events_json(
            engine, drug, OUTPUT_DIR / f"{drug}.json"
        )
        logger.info("Exported %s.json (%d rows)", drug, n_ae)

    # ── Step 4: Generate AI summaries (incremental) ─────────────────────
    logger.info("Generating AI plain-language summaries...")
    summaries_path = OUTPUT_DIR / "summaries.json"
    summaries = generate_summaries(
        OUTPUT_DIR / "signals.json", existing_path=summaries_path
    )
    if summaries:
        n_sum = export_summaries_json(summaries, OUTPUT_DIR / "summaries.json")
        logger.info("Exported summaries.json (%d drugs)", n_sum)
    else:
        logger.warning("No summaries generated (missing API key or no flagged signals)")

    logger.info("Refresh complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
