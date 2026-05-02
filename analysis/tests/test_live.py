"""Live integration test: compute_all_signals against real FAERS data.

WHY A SECOND DRUG IS NEEDED
Disproportionality analysis requires a background population of *other* drugs.
With only one drug in adverse_events, every 2×2 table has c=0 (no other drug
reports the reaction), making ROR/PRR undefined. This fixture ensures aspirin
is present alongside ibuprofen so the background population is non-trivial.

RUNNING THIS TEST
    pytest analysis/tests/test_live.py -v -s

    First run fetches ~1000 aspirin records from OpenFDA (~5–10 s).
    Subsequent runs reuse the already-loaded data.

    Requires db/pharos.db with ibuprofen data loaded (run pipeline first).
    Skipped automatically if the DB does not exist.
"""

import pytest
import pandas as pd
from pathlib import Path
from sqlalchemy import text

from pipeline.db import get_engine, create_tables, insert_adverse_events
from pipeline.ingest import fetch_adverse_events
from pipeline.clean import clean_adverse_events
from analysis.disproportionality import compute_all_signals, flag_signal

DB_PATH = Path("db/pharos.db")

_SCHEMA_COLS = [
    "drug_name", "reaction", "ror", "ror_lower", "ror_upper",
    "prr", "n_reports", "computed_date",
]


@pytest.fixture(scope="module")
def engine():
    """Engine backed by pharos.db; ensures at least two drugs are loaded."""
    if not DB_PATH.exists():
        pytest.skip("db/pharos.db not found — run `python pipeline/run_refresh.py` first")

    eng = get_engine(DB_PATH)
    create_tables(eng)

    with eng.connect() as conn:
        n_drugs = pd.read_sql(
            text("SELECT COUNT(DISTINCT drug_name) AS n FROM adverse_events"), conn
        ).iloc[0]["n"]

    if n_drugs < 2:
        # Fetch aspirin to provide a background population
        print("\n[fixture] Only one drug in DB — fetching aspirin for background...")
        raw = fetch_adverse_events("aspirin", max_records=1000)
        clean = clean_adverse_events(raw)
        if not clean.empty:
            insert_adverse_events(eng, clean)
            print(f"[fixture] Loaded {len(clean)} aspirin rows")
        else:
            pytest.skip("Could not fetch aspirin data — check API key and network")

    return eng


@pytest.fixture(scope="module")
def signals(engine):
    """Run compute_all_signals once and share the result across tests."""
    return compute_all_signals(engine)


# ── Schema and shape ─────────────────────────────────────────────────────────

def test_returns_dataframe(signals):
    assert isinstance(signals, pd.DataFrame)


def test_schema_columns_present(signals):
    for col in _SCHEMA_COLS:
        assert col in signals.columns, f"Missing column: {col}"


def test_chi_squared_column_present(signals):
    assert "chi_squared" in signals.columns


def test_nonempty(signals):
    assert not signals.empty, (
        "compute_all_signals returned an empty DataFrame — "
        "check that multiple drugs are in adverse_events"
    )


def test_ror_values_positive(signals):
    assert (signals["ror"] > 0).all()


def test_ci_ordering(signals):
    """Lower CI must be below the point estimate, upper must be above."""
    assert (signals["ror_lower"] < signals["ror"]).all()
    assert (signals["ror_upper"] > signals["ror"]).all()


def test_n_reports_positive(signals):
    assert (signals["n_reports"] > 0).all()


# ── Signal detection ─────────────────────────────────────────────────────────

def test_at_least_one_flagged_signal(signals):
    """At least one drug-reaction pair must meet all four thresholds."""
    flagged = signals[
        (signals["ror_lower"] > 1.0)
        & (signals["prr"] >= 2.0)
        & (signals["n_reports"] >= 3)
        & (signals["chi_squared"] >= 4.0)
    ]
    assert not flagged.empty, (
        "No pairs met all four signal criteria "
        "(ror_lower>1, prr≥2, n≥3, χ²≥4)"
    )


def test_flag_signal_consistent_with_row_criteria(signals):
    """flag_signal() must agree with direct column comparisons."""
    for _, row in signals.head(50).iterrows():
        ror_result = {
            "ror": row["ror"],
            "ror_lower": row["ror_lower"],
            "ror_upper": row["ror_upper"],
            "n_reports": row["n_reports"],
        }
        prr_result = {
            "prr": row["prr"],
            "chi_squared": row["chi_squared"],
            "n_reports": row["n_reports"],
        }
        expected = (
            row["ror_lower"] > 1.0
            and row["prr"] >= 2.0
            and row["n_reports"] >= 3
            and row["chi_squared"] >= 4.0
        )
        assert flag_signal(ror_result, prr_result) == expected


# ── Print top 10 by ROR (informational) ──────────────────────────────────────

def test_print_top_10_signals_by_ror(signals, capsys):
    top10 = signals.nlargest(10, "ror")[
        ["drug_name", "reaction", "ror", "ror_lower", "ror_upper", "prr", "n_reports"]
    ].round(3)

    with capsys.disabled():
        print("\n")
        print("=" * 70)
        print("  Top 10 drug-reaction pairs by ROR (ibuprofen + aspirin data)")
        print("=" * 70)
        print(top10.to_string(index=False))
        print("=" * 70)

    assert len(top10) > 0
