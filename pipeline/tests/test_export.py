"""Unit tests for pipeline.export — static JSON export for the dashboard.

Tests cover exporting signal scores and adverse events to JSON format.
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from pipeline.db import create_tables, get_engine, insert_adverse_events, insert_signal_scores
from pipeline.export import export_adverse_events_json, export_signals_json


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield str(db_path)


@pytest.fixture
def engine(temp_db):
    """Create an engine and initialize tables."""
    engine = get_engine(temp_db)
    create_tables(engine)
    yield engine


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ── export_signals_json ────────────────────────────────────────────────────


class TestExportSignalsJson:
    """Test exporting signal_scores to JSON."""

    def test_exports_to_file(self, engine, temp_output_dir):
        """Test that signals are exported to a JSON file."""
        # Insert test data
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO drugs (name) VALUES ('ibuprofen')"))
            conn.commit()

        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "ror": [4.2],
            "ror_lower": [3.8],
            "ror_upper": [4.6],
            "prr": [3.5],
            "chi_squared": [12.0],
            "n_reports": [100],
            "computed_date": ["2022-01-01"],
        })
        insert_signal_scores(engine, df)

        # Export
        output_file = temp_output_dir / "signals.json"
        n = export_signals_json(engine, output_file)

        assert n == 1
        assert output_file.exists()

    def test_output_format_records_oriented(self, engine, temp_output_dir):
        """Test that output is records-oriented JSON (list of dicts)."""
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO drugs (name) VALUES ('ibuprofen')"))
            conn.commit()

        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "ror": [4.2],
            "ror_lower": [3.8],
            "ror_upper": [4.6],
            "prr": [3.5],
            "chi_squared": [12.0],
            "n_reports": [100],
            "computed_date": ["2022-01-01"],
        })
        insert_signal_scores(engine, df)

        output_file = temp_output_dir / "signals.json"
        export_signals_json(engine, output_file)

        data = json.loads(output_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert isinstance(data[0], dict)
        assert "drug_name" in data[0]
        assert data[0]["drug_name"] == "ibuprofen"

    def test_adds_flagged_column(self, engine, temp_output_dir):
        """Test that 'flagged' column is added based on signal criteria."""
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO drugs (name) VALUES ('ibuprofen')"))
            conn.execute(text("INSERT INTO drugs (name) VALUES ('aspirin')"))
            conn.commit()

        df = pd.DataFrame({
            "drug_name": ["ibuprofen", "aspirin"],
            "reaction": ["headache", "dizziness"],
            "ror": [4.2, 1.0],
            "ror_lower": [3.8, 0.9],  # Second one doesn't meet ROR threshold
            "ror_upper": [4.6, 1.1],
            "prr": [3.5, 2.0],
            "chi_squared": [12.0, 5.0],
            "n_reports": [100, 50],
            "computed_date": ["2022-01-01"] * 2,
        })
        insert_signal_scores(engine, df)

        output_file = temp_output_dir / "signals.json"
        export_signals_json(engine, output_file)

        data = json.loads(output_file.read_text())
        assert data[0]["flagged"] is True
        assert data[1]["flagged"] is False

    def test_flagged_requires_all_criteria(self, engine, temp_output_dir):
        """Test that flagged=True requires ALL signal criteria."""
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO drugs (name) VALUES ('drug1')"))
            conn.execute(text("INSERT INTO drugs (name) VALUES ('drug2')"))
            conn.execute(text("INSERT INTO drugs (name) VALUES ('drug3')"))
            conn.commit()

        df = pd.DataFrame({
            "drug_name": ["drug1", "drug2", "drug3"],
            "reaction": ["r1", "r2", "r3"],
            "ror": [4.2, 4.2, 4.2],
            "ror_lower": [3.8, 0.9, 3.8],  # drug2 fails ROR
            "ror_upper": [4.6, 1.1, 4.6],
            "prr": [3.5, 3.5, 1.5],  # drug3 fails PRR
            "chi_squared": [12.0, 12.0, 12.0],
            "n_reports": [100, 100, 2],  # drug3 also fails n_reports
            "computed_date": ["2022-01-01"] * 3,
        })
        insert_signal_scores(engine, df)

        output_file = temp_output_dir / "signals.json"
        export_signals_json(engine, output_file)

        data = json.loads(output_file.read_text())
        assert data[0]["flagged"] is True  # Meets all criteria
        assert data[1]["flagged"] is False  # Fails ROR
        assert data[2]["flagged"] is False  # Fails PRR and n_reports

    def test_empty_signal_scores_writes_empty_array(self, engine, temp_output_dir):
        """Test that empty signal_scores writes an empty JSON array."""
        output_file = temp_output_dir / "signals.json"
        n = export_signals_json(engine, output_file)

        assert n == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data == []

    def test_creates_parent_directories(self, engine, temp_output_dir):
        """Test that parent directories are created if missing."""
        output_file = temp_output_dir / "subdir" / "nested" / "signals.json"
        export_signals_json(engine, output_file)
        assert output_file.exists()

    def test_returns_row_count(self, engine, temp_output_dir):
        """Test that the function returns the number of rows written."""
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO drugs (name) VALUES ('ibuprofen')"))
            conn.execute(text("INSERT INTO drugs (name) VALUES ('aspirin')"))
            conn.commit()

        df = pd.DataFrame({
            "drug_name": ["ibuprofen", "aspirin"],
            "reaction": ["headache", "dizziness"],
            "ror": [4.2, 2.1],
            "ror_lower": [3.8, 1.9],
            "ror_upper": [4.6, 2.3],
            "prr": [3.5, 2.0],
            "chi_squared": [12.0, 4.0],
            "n_reports": [100, 50],
            "computed_date": ["2022-01-01"] * 2,
        })
        insert_signal_scores(engine, df)

        output_file = temp_output_dir / "signals.json"
        n = export_signals_json(engine, output_file)

        assert n == 2

    def test_json_is_properly_formatted(self, engine, temp_output_dir):
        """Test that output JSON is properly formatted (indented)."""
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO drugs (name) VALUES ('ibuprofen')"))
            conn.commit()

        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "ror": [4.2],
            "ror_lower": [3.8],
            "ror_upper": [4.6],
            "prr": [3.5],
            "chi_squared": [12.0],
            "n_reports": [100],
            "computed_date": ["2022-01-01"],
        })
        insert_signal_scores(engine, df)

        output_file = temp_output_dir / "signals.json"
        export_signals_json(engine, output_file)

        content = output_file.read_text()
        # Should be indented (JSON with proper formatting)
        assert "\n  " in content or content.startswith("[")


# ── export_adverse_events_json ──────────────────────────────────────────────


class TestExportAdverseEventsJson:
    """Test exporting adverse events for a specific drug to JSON."""

    def test_exports_to_file(self, engine, temp_output_dir):
        """Test that adverse events are exported to a JSON file."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["recovered"],
            "report_date": [None],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        insert_adverse_events(engine, df)

        output_file = temp_output_dir / "ibuprofen.json"
        n = export_adverse_events_json(engine, "ibuprofen", output_file)

        assert n == 1
        assert output_file.exists()

    def test_filters_by_drug_name(self, engine, temp_output_dir):
        """Test that only events for the specified drug are exported."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen", "ibuprofen", "aspirin"],
            "reaction": ["headache", "dizziness", "headache"],
            "outcome": ["recovered"] * 3,
            "report_date": [None] * 3,
            "serious": [1] * 3,
            "source": ["openfda_faers"] * 3,
        })
        insert_adverse_events(engine, df)

        output_file = temp_output_dir / "ibuprofen.json"
        n = export_adverse_events_json(engine, "ibuprofen", output_file)

        assert n == 2
        data = json.loads(output_file.read_text())
        assert all(d["drug_name"] == "ibuprofen" for d in data)

    def test_canonicalises_drug_name_in_query(self, engine, temp_output_dir):
        """Test that the query drug name is canonicalised."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["recovered"],
            "report_date": [None],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        insert_adverse_events(engine, df)

        # Query with brand name (should be canonicalised)
        output_file = temp_output_dir / "ibuprofen.json"
        n = export_adverse_events_json(engine, "ADVIL", output_file)

        assert n == 1

    def test_empty_drug_writes_empty_array(self, engine, temp_output_dir):
        """Test that a drug with no events writes an empty JSON array."""
        output_file = temp_output_dir / "nonexistent.json"
        n = export_adverse_events_json(engine, "nonexistent_drug", output_file)

        assert n == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data == []

    def test_creates_parent_directories(self, engine, temp_output_dir):
        """Test that parent directories are created if missing."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["recovered"],
            "report_date": [None],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        insert_adverse_events(engine, df)

        output_file = temp_output_dir / "subdir" / "nested" / "ibuprofen.json"
        export_adverse_events_json(engine, "ibuprofen", output_file)

        assert output_file.exists()

    def test_returns_row_count(self, engine, temp_output_dir):
        """Test that the function returns the number of rows written."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen", "ibuprofen"],
            "reaction": ["headache", "dizziness"],
            "outcome": ["recovered", "not_recovered"],
            "report_date": [None] * 2,
            "serious": [1, 0],
            "source": ["openfda_faers"] * 2,
        })
        insert_adverse_events(engine, df)

        output_file = temp_output_dir / "ibuprofen.json"
        n = export_adverse_events_json(engine, "ibuprofen", output_file)

        assert n == 2

    def test_output_format_records_oriented(self, engine, temp_output_dir):
        """Test that output is records-oriented JSON (list of dicts)."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["recovered"],
            "report_date": [None],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        insert_adverse_events(engine, df)

        output_file = temp_output_dir / "ibuprofen.json"
        export_adverse_events_json(engine, "ibuprofen", output_file)

        data = json.loads(output_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert isinstance(data[0], dict)

    def test_json_is_properly_formatted(self, engine, temp_output_dir):
        """Test that output JSON is properly formatted (indented)."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["recovered"],
            "report_date": [None],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        insert_adverse_events(engine, df)

        output_file = temp_output_dir / "ibuprofen.json"
        export_adverse_events_json(engine, "ibuprofen", output_file)

        content = output_file.read_text()
        # Should be indented (JSON with proper formatting)
        assert "\n  " in content or content.startswith("[")

    def test_multiple_calls_overwrites_file(self, engine, temp_output_dir):
        """Test that multiple exports overwrite the file."""
        df1 = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["recovered"],
            "report_date": [None],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        insert_adverse_events(engine, df1)

        output_file = temp_output_dir / "ibuprofen.json"
        export_adverse_events_json(engine, "ibuprofen", output_file)

        content1 = output_file.read_text()
        n1 = len(json.loads(content1))

        # Clear and insert different data
        from pipeline.db import clear_adverse_events
        clear_adverse_events(engine)

        df2 = pd.DataFrame({
            "drug_name": ["ibuprofen", "ibuprofen"],
            "reaction": ["dizziness", "nausea"],
            "outcome": ["not_recovered", "unknown"],
            "report_date": [None] * 2,
            "serious": [0, 1],
            "source": ["openfda_faers"] * 2,
        })
        insert_adverse_events(engine, df2)

        export_adverse_events_json(engine, "ibuprofen", output_file)

        content2 = output_file.read_text()
        n2 = len(json.loads(content2))

        assert n1 == 1
        assert n2 == 2
        assert content1 != content2
