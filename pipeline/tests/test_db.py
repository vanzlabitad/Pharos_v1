"""Unit tests for pipeline.db — SQLite interface using SQLAlchemy.

Tests cover engine creation, table creation, insertions, deduplication,
and foreign key enforcement.
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from pipeline.db import (
    clear_adverse_events,
    clear_signal_scores,
    create_tables,
    get_engine,
    insert_adverse_events,
    insert_signal_scores,
    seed_drug_aliases,
)


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


# ── get_engine ──────────────────────────────────────────────────────────────


class TestGetEngine:
    """Test engine creation and configuration."""

    def test_creates_engine_for_path(self, temp_db):
        """Test that get_engine creates a valid SQLAlchemy engine."""
        engine = get_engine(temp_db)
        assert engine is not None
        # Verify we can execute a query
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_creates_parent_directory(self):
        """Test that get_engine creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "test.db"
            engine = get_engine(db_path)
            # Parent directory should exist even if the .db file doesn't yet
            assert db_path.parent.exists()

    def test_foreign_keys_enabled(self, engine):
        """Test that foreign key constraints are enabled."""
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys"))
            fk_status = result.scalar()
            assert fk_status == 1

    def test_none_db_path_uses_default(self, monkeypatch):
        """Test that None db_path uses environment variable or default."""
        monkeypatch.delenv("DB_PATH", raising=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.chdir(tmpdir)
            engine = get_engine(None)
            assert engine is not None

    def test_string_path_accepted(self, temp_db):
        """Test that string paths are accepted."""
        engine = get_engine(temp_db)
        assert engine is not None

    def test_path_object_accepted(self, temp_db):
        """Test that Path objects are accepted."""
        engine = get_engine(Path(temp_db))
        assert engine is not None


# ── create_tables ──────────────────────────────────────────────────────────


class TestCreateTables:
    """Test schema creation."""

    def test_creates_drugs_table(self, engine):
        """Test that drugs table is created."""
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='drugs'"
            ))
            assert result.scalar() == "drugs"

    def test_creates_adverse_events_table(self, engine):
        """Test that adverse_events table is created."""
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='adverse_events'"
            ))
            assert result.scalar() == "adverse_events"

    def test_creates_signal_scores_table(self, engine):
        """Test that signal_scores table is created."""
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='signal_scores'"
            ))
            assert result.scalar() == "signal_scores"

    def test_creates_drug_aliases_table(self, engine):
        """Test that drug_aliases table is created."""
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='drug_aliases'"
            ))
            assert result.scalar() == "drug_aliases"

    def test_idempotent(self, engine):
        """Test that create_tables is idempotent."""
        # Should not raise on second call
        create_tables(engine)
        create_tables(engine)

    def test_drugs_table_has_name_column(self, engine):
        """Test that drugs table has name column."""
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(drugs)"))
            columns = {row[1] for row in result}
            assert "name" in columns

    def test_adverse_events_has_required_columns(self, engine):
        """Test that adverse_events table has required columns."""
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(adverse_events)"))
            columns = {row[1] for row in result}
            required = {"drug_name", "reaction", "outcome", "report_date", "serious", "source"}
            assert required.issubset(columns)


# ── insert_adverse_events ──────────────────────────────────────────────────


class TestInsertAdverseEvents:
    """Test inserting adverse event data."""

    def test_empty_dataframe_returns_zero(self, engine):
        """Test that inserting empty DataFrame returns 0."""
        df = pd.DataFrame()
        n = insert_adverse_events(engine, df)
        assert n == 0

    def test_raises_on_missing_columns(self, engine):
        """Test that missing columns raise ValueError."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            # Missing other required columns
        })
        with pytest.raises(ValueError, match="missing required columns"):
            insert_adverse_events(engine, df)

    def test_inserts_single_row(self, engine):
        """Test inserting a single adverse event."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["recovered"],
            "report_date": [None],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        n = insert_adverse_events(engine, df)
        assert n == 1

        # Verify it's in the database
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM adverse_events WHERE drug_name = 'ibuprofen'"
            ))
            assert result.scalar() == 1

    def test_inserts_multiple_rows(self, engine):
        """Test inserting multiple rows."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen", "ibuprofen", "aspirin"],
            "reaction": ["headache", "dizziness", "headache"],
            "outcome": ["recovered", "not_recovered", "unknown"],
            "report_date": [None] * 3,
            "serious": [1, 0, 1],
            "source": ["openfda_faers"] * 3,
        })
        n = insert_adverse_events(engine, df)
        assert n == 3

        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM adverse_events"))
            assert result.scalar() == 3

    def test_creates_drug_entries(self, engine):
        """Test that distinct drug names are inserted into drugs table."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen", "ibuprofen", "aspirin"],
            "reaction": ["headache", "dizziness", "headache"],
            "outcome": ["recovered", "not_recovered", "unknown"],
            "report_date": [None] * 3,
            "serious": [1, 0, 1],
            "source": ["openfda_faers"] * 3,
        })
        insert_adverse_events(engine, df)

        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM drugs WHERE name IN ('ibuprofen', 'aspirin')"
            ))
            assert result.scalar() == 2

    def test_ignores_duplicate_drugs(self, engine):
        """Test that duplicate drugs in the drugs table are handled (INSERT OR IGNORE)."""
        df1 = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["recovered"],
            "report_date": [None],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        df2 = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["dizziness"],
            "outcome": ["not_recovered"],
            "report_date": [None],
            "serious": [0],
            "source": ["openfda_faers"],
        })
        insert_adverse_events(engine, df1)
        insert_adverse_events(engine, df2)

        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM drugs WHERE name = 'ibuprofen'"
            ))
            assert result.scalar() == 1

    def test_foreign_key_constraint_enforced(self, engine):
        """Test that foreign key constraint is enforced."""
        # Try to insert with a drug that doesn't exist in drugs table
        with engine.connect() as conn:
            # First clear the drugs table
            conn.execute(text("DELETE FROM drugs"))
            conn.commit()

            # Try to insert an adverse event — should fail
            with pytest.raises(Exception):  # IntegrityError or similar
                conn.execute(text(
                    "INSERT INTO adverse_events (drug_name, reaction, outcome, report_date, serious, source) "
                    "VALUES ('nonexistent', 'headache', 'recovered', NULL, 1, 'openfda_faers')"
                ))
                conn.commit()


# ── insert_signal_scores ────────────────────────────────────────────────────


class TestInsertSignalScores:
    """Test inserting signal scores."""

    def test_empty_dataframe_returns_zero(self, engine):
        """Test that inserting empty DataFrame returns 0."""
        df = pd.DataFrame()
        n = insert_signal_scores(engine, df)
        assert n == 0

    def test_raises_on_missing_columns(self, engine):
        """Test that missing columns raise ValueError."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            # Missing other required columns
        })
        with pytest.raises(ValueError, match="missing required columns"):
            insert_signal_scores(engine, df)

    def test_inserts_single_score(self, engine):
        """Test inserting a single signal score."""
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
        # First insert a drug to satisfy FK
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO drugs (name) VALUES ('ibuprofen')"))
            conn.commit()

        n = insert_signal_scores(engine, df)
        assert n == 1

        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM signal_scores WHERE drug_name = 'ibuprofen'"
            ))
            assert result.scalar() == 1

    def test_inserts_multiple_scores(self, engine):
        """Test inserting multiple signal scores."""
        # First insert drugs
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO drugs (name) VALUES ('ibuprofen')"))
            conn.execute(text("INSERT INTO drugs (name) VALUES ('aspirin')"))
            conn.commit()

        df = pd.DataFrame({
            "drug_name": ["ibuprofen", "ibuprofen", "aspirin"],
            "reaction": ["headache", "dizziness", "headache"],
            "ror": [4.2, 2.1, 3.0],
            "ror_lower": [3.8, 1.9, 2.5],
            "ror_upper": [4.6, 2.3, 3.5],
            "prr": [3.5, 2.0, 2.8],
            "chi_squared": [12.0, 4.0, 10.0],
            "n_reports": [100, 50, 75],
            "computed_date": ["2022-01-01"] * 3,
        })
        n = insert_signal_scores(engine, df)
        assert n == 3

        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM signal_scores"))
            assert result.scalar() == 3


# ── seed_drug_aliases ──────────────────────────────────────────────────────


class TestSeedDrugAliases:
    """Test seeding drug aliases from JSON file."""

    def test_returns_zero_when_file_missing(self, engine, monkeypatch):
        """Test that missing alias file returns 0."""
        # Monkeypatch to return a non-existent file path
        monkeypatch.setattr(
            "pipeline.db._ALIASES_PATH",
            Path("/nonexistent/path/drug_aliases.json")
        )
        n = seed_drug_aliases(engine)
        assert n == 0

    def test_seeds_aliases_from_json(self, engine, tmp_path, monkeypatch):
        """Test seeding aliases from a JSON file."""
        # Create a temporary alias file
        aliases_file = tmp_path / "drug_aliases.json"
        aliases_file.write_text(json.dumps({
            "ADVIL": "ibuprofen",
            "Motrin": "ibuprofen",
            "Tylenol": "acetaminophen",
        }))

        monkeypatch.setattr("pipeline.db._ALIASES_PATH", aliases_file)

        n = seed_drug_aliases(engine)
        assert n == 3

        # Verify aliases are in the database
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM drug_aliases"))
            assert result.scalar() == 3

    def test_creates_canonical_drugs(self, engine, tmp_path, monkeypatch):
        """Test that canonical drug names are created in drugs table."""
        aliases_file = tmp_path / "drug_aliases.json"
        aliases_file.write_text(json.dumps({
            "ADVIL": "ibuprofen",
            "Motrin": "ibuprofen",
            "Tylenol": "acetaminophen",
        }))

        monkeypatch.setattr("pipeline.db._ALIASES_PATH", aliases_file)

        seed_drug_aliases(engine)

        # Verify canonical drugs are in the drugs table
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM drugs WHERE name IN ('ibuprofen', 'acetaminophen')"
            ))
            assert result.scalar() == 2

    def test_idempotent_insert_or_replace(self, engine, tmp_path, monkeypatch):
        """Test that re-seeding with updated aliases replaces old ones."""
        aliases_file = tmp_path / "drug_aliases.json"
        aliases_file.write_text(json.dumps({
            "ADVIL": "ibuprofen",
        }))

        monkeypatch.setattr("pipeline.db._ALIASES_PATH", aliases_file)

        n1 = seed_drug_aliases(engine)
        assert n1 == 1

        # Update the alias file
        aliases_file.write_text(json.dumps({
            "ADVIL": "ibuprofen",
            "Motrin": "ibuprofen",
        }))

        n2 = seed_drug_aliases(engine)
        assert n2 == 2

        # Should have 2 aliases total
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM drug_aliases"))
            assert result.scalar() == 2

    def test_normalises_keys_and_values(self, engine, tmp_path, monkeypatch):
        """Test that alias keys and values are normalised (lowercase, stripped)."""
        aliases_file = tmp_path / "drug_aliases.json"
        aliases_file.write_text(json.dumps({
            "  ADVIL  ": "  Ibuprofen  ",
        }))

        monkeypatch.setattr("pipeline.db._ALIASES_PATH", aliases_file)

        seed_drug_aliases(engine)

        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT alias, canonical_name FROM drug_aliases WHERE alias = 'advil'"
            ))
            row = result.fetchone()
            assert row is not None
            assert row[0] == "advil"
            assert row[1] == "ibuprofen"


# ── clear_adverse_events ────────────────────────────────────────────────────


class TestClearAdverseEvents:
    """Test clearing adverse events table."""

    def test_clears_all_rows(self, engine):
        """Test that clear_adverse_events removes all rows."""
        # Insert some data
        df = pd.DataFrame({
            "drug_name": ["ibuprofen", "aspirin"],
            "reaction": ["headache", "headache"],
            "outcome": ["recovered", "recovered"],
            "report_date": [None] * 2,
            "serious": [1] * 2,
            "source": ["openfda_faers"] * 2,
        })
        insert_adverse_events(engine, df)

        # Verify data is there
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM adverse_events"))
            assert result.scalar() == 2

        # Clear
        clear_adverse_events(engine)

        # Verify table is empty
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM adverse_events"))
            assert result.scalar() == 0

    def test_idempotent(self, engine):
        """Test that clearing an already-empty table is idempotent."""
        clear_adverse_events(engine)
        clear_adverse_events(engine)  # Should not raise


# ── clear_signal_scores ────────────────────────────────────────────────────


class TestClearSignalScores:
    """Test clearing signal scores table."""

    def test_clears_all_rows(self, engine):
        """Test that clear_signal_scores removes all rows."""
        # First create drugs
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO drugs (name) VALUES ('ibuprofen')"))
            conn.commit()

        # Insert some data
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

        # Verify data is there
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM signal_scores"))
            assert result.scalar() == 1

        # Clear
        clear_signal_scores(engine)

        # Verify table is empty
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM signal_scores"))
            assert result.scalar() == 0

    def test_idempotent(self, engine):
        """Test that clearing an already-empty table is idempotent."""
        clear_signal_scores(engine)
        clear_signal_scores(engine)  # Should not raise
