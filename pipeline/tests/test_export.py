"""Unit tests for pipeline.export JSON exporters.

Each test spins up a fresh in-memory SQLite database via the production
``pipeline.db.get_engine`` + ``create_tables`` path so the schema, FK
enforcement, and connection lifecycle exactly match what runs in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.db import create_tables, get_engine, insert_signal_scores
from pipeline.export import export_adverse_events_json, export_signals_json


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    """A fresh on-disk SQLite engine with the production schema applied.

    On-disk (not :memory:) so the connect-time ``PRAGMA foreign_keys = ON``
    hook installed by ``get_engine`` behaves identically to production.
    """
    eng = get_engine(tmp_path / "test.db")
    create_tables(eng)
    return eng


def _seed_drug(engine: Engine, name: str) -> None:
    """Insert a drug into the drugs index so FKs are satisfied."""
    with engine.connect() as conn:
        conn.execute(text("INSERT OR IGNORE INTO drugs (name) VALUES (:n)"), {"n": name})
        conn.commit()


def _seed_signal_scores(engine: Engine) -> int:
    """Insert a small mix of flagged and non-flagged signal rows.

    Returns the number of rows inserted. Two rows are EVANS-positive
    (ibuprofen + aspirin) and one is below threshold (metformin).
    """
    _seed_drug(engine, "ibuprofen")
    _seed_drug(engine, "aspirin")
    _seed_drug(engine, "metformin")

    df = pd.DataFrame(
        [
            # flagged: all four criteria pass
            {
                "drug_name": "ibuprofen", "reaction": "gi bleeding",
                "ror": 4.2, "ror_lower": 3.8, "ror_upper": 4.6,
                "prr": 3.5, "chi_squared": 120.0, "n_reports": 50,
                "computed_date": "2026-06-01",
            },
            # flagged: at the boundary (PRR == 2, n == 3, χ² == 4)
            {
                "drug_name": "aspirin", "reaction": "tinnitus",
                "ror": 2.1, "ror_lower": 1.05, "ror_upper": 4.2,
                "prr": 2.0, "chi_squared": 4.0, "n_reports": 3,
                "computed_date": "2026-06-01",
            },
            # not flagged: ROR CI crosses 1
            {
                "drug_name": "metformin", "reaction": "headache",
                "ror": 1.1, "ror_lower": 0.9, "ror_upper": 1.3,
                "prr": 1.05, "chi_squared": 0.5, "n_reports": 200,
                "computed_date": "2026-06-01",
            },
        ]
    )
    return insert_signal_scores(engine, df)


def _seed_adverse_events(engine: Engine, drug: str, n: int) -> None:
    """Insert ``n`` adverse-event rows for the given canonical drug name."""
    _seed_drug(engine, drug)
    rows = [
        {
            "drug_name": drug,
            "reaction": f"reaction_{i}",
            "outcome": "hospitalisation",
            "report_date": "2026-05-01",
            "serious": 1,
            "source": "FAERS",
        }
        for i in range(n)
    ]
    df = pd.DataFrame(rows)
    with engine.connect() as conn:
        df.to_sql("adverse_events", conn, if_exists="append", index=False)
        conn.commit()


# ── export_signals_json ────────────────────────────────────────────────


class TestExportSignalsJson:
    def test_writes_records_oriented_file(self, engine: Engine, tmp_path: Path) -> None:
        n_inserted = _seed_signal_scores(engine)
        out = tmp_path / "out" / "signals.json"

        n_written = export_signals_json(engine, out)

        assert n_written == n_inserted == 3
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(payload, list)
        assert len(payload) == 3
        # Records-oriented: each element is a dict keyed by column name.
        assert {"drug_name", "reaction", "ror", "prr", "n_reports"} <= payload[0].keys()

    def test_adds_flagged_column_using_evans_criterion(
        self, engine: Engine, tmp_path: Path
    ) -> None:
        _seed_signal_scores(engine)
        out = tmp_path / "signals.json"

        export_signals_json(engine, out)

        payload = json.loads(out.read_text(encoding="utf-8"))
        flagged_by_drug = {row["drug_name"]: row["flagged"] for row in payload}
        assert flagged_by_drug == {
            "ibuprofen": True,    # clear signal
            "aspirin":   True,    # boundary case — inclusive thresholds
            "metformin": False,   # ROR CI crosses 1
        }

    def test_empty_table_writes_empty_array(self, engine: Engine, tmp_path: Path) -> None:
        out = tmp_path / "signals.json"

        n_written = export_signals_json(engine, out)

        assert n_written == 0
        assert out.read_text(encoding="utf-8") == "[]"

    def test_creates_parent_directories(self, engine: Engine, tmp_path: Path) -> None:
        _seed_signal_scores(engine)
        out = tmp_path / "deeply" / "nested" / "signals.json"

        export_signals_json(engine, out)

        assert out.exists()


# ── export_adverse_events_json ─────────────────────────────────────────


class TestExportAdverseEventsJson:
    def test_writes_records_oriented_file(self, engine: Engine, tmp_path: Path) -> None:
        _seed_adverse_events(engine, "ibuprofen", n=5)
        out = tmp_path / "ibuprofen.json"

        n_written = export_adverse_events_json(engine, "ibuprofen", out)

        assert n_written == 5
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert len(payload) == 5
        assert all(row["drug_name"] == "ibuprofen" for row in payload)

    def test_canonicalises_brand_name_before_lookup(
        self, engine: Engine, tmp_path: Path
    ) -> None:
        # DB holds the canonical generic; caller passes the brand name.
        _seed_adverse_events(engine, "ibuprofen", n=2)
        out = tmp_path / "advil.json"

        n_written = export_adverse_events_json(engine, "ADVIL", out)

        assert n_written == 2
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert all(row["drug_name"] == "ibuprofen" for row in payload)

    def test_unknown_drug_writes_empty_array(self, engine: Engine, tmp_path: Path) -> None:
        out = tmp_path / "nonsense.json"

        n_written = export_adverse_events_json(engine, "not_a_real_drug", out)

        assert n_written == 0
        assert out.read_text(encoding="utf-8") == "[]"

    def test_creates_parent_directories(self, engine: Engine, tmp_path: Path) -> None:
        _seed_adverse_events(engine, "ibuprofen", n=1)
        out = tmp_path / "deeply" / "nested" / "ibuprofen.json"

        export_adverse_events_json(engine, "ibuprofen", out)

        assert out.exists()
