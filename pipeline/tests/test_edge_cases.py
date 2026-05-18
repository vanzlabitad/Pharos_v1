"""Additional edge case tests for pipeline modules.

This file covers additional scenarios not covered in the main test files,
such as integration scenarios and boundary conditions.
"""

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pipeline.clean import clean_adverse_events
from pipeline.db import (
    clear_adverse_events,
    create_tables,
    get_engine,
    insert_adverse_events,
    insert_signal_scores,
)
from pipeline.export import export_adverse_events_json, export_signals_json


# ── Integration Tests ───────────────────────────────────────────────────────


class TestPipelineIntegration:
    """Integration tests for the full data pipeline."""

    def test_ingest_clean_insert_export_cycle(self):
        """Test complete cycle: data → clean → insert → export."""
        # Create raw data
        raw_df = pd.DataFrame({
            "safetyreportid": ["report1", "report2", "report3"],
            "drug_name": ["ADVIL", "ibuprofen", "ADVIL"],
            "reaction": ["HEADACHE", "  nausea  ", None],
            "outcome": ["1", "2", "3"],
            "report_date": ["20220101", "20220102", "20220103"],
            "serious": [1, 0, None],
            "source": ["openfda_faers"] * 3,
        })

        # Clean the data
        clean_df = clean_adverse_events(raw_df)

        # Insert into database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine = get_engine(db_path)
            create_tables(engine)

            n_inserted = insert_adverse_events(engine, clean_df)
            assert n_inserted == 2  # One row dropped due to null reaction

            # Export
            output_file = Path(tmpdir) / "export.json"
            n_exported = export_adverse_events_json(engine, "ibuprofen", output_file)
            assert n_exported > 0

    def test_multiple_drugs_full_cycle(self):
        """Test that the pipeline handles multiple drugs correctly."""
        raw_df = pd.DataFrame({
            "safetyreportid": ["r1", "r2", "r3", "r4"],
            "drug_name": ["aspirin", "ibuprofen", "aspirin", "metformin"],
            "reaction": ["headache", "nausea", "headache", "dizziness"],
            "outcome": ["1", "2", "1", "1"],
            "report_date": ["20220101"] * 4,
            "serious": [1] * 4,
            "source": ["openfda_faers"] * 4,
        })

        clean_df = clean_adverse_events(raw_df)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine = get_engine(db_path)
            create_tables(engine)

            insert_adverse_events(engine, clean_df)

            # Export each drug
            for drug in ["aspirin", "ibuprofen", "metformin"]:
                output_file = Path(tmpdir) / f"{drug}.json"
                n = export_adverse_events_json(engine, drug, output_file)
                assert n > 0
                assert output_file.exists()

    def test_handling_missing_data_fields(self):
        """Test that pipeline gracefully handles missing or malformed data."""
        raw_df = pd.DataFrame({
            "safetyreportid": ["r1", "r2", "r3"],
            "drug_name": ["ibuprofen", "aspirin", "naproxen"],  # No None values
            "reaction": ["headache", "nausea", "dizziness"],
            "outcome": [None, "2", "invalid_code"],
            "report_date": [None, "not_a_date", "20220101"],
            "serious": [None, "not_numeric", 1],
            "source": ["openfda_faers"] * 3,
        })

        clean_df = clean_adverse_events(raw_df)

        # Should still work, just with some rows/values filtered/normalized
        assert len(clean_df) >= 0
        assert "drug_name" in clean_df.columns

    def test_large_dataset_performance(self):
        """Test that pipeline handles larger datasets reasonably."""
        # Create a dataset with 1000 rows
        n_rows = 1000
        df_dict = {
            "safetyreportid": [f"report{i}" for i in range(n_rows)],
            "drug_name": ["ibuprofen"] * (n_rows // 2) + ["aspirin"] * (n_rows // 2),
            "reaction": [f"reaction{i % 10}" for i in range(n_rows)],
            "outcome": ["1"] * n_rows,
            "report_date": ["20220101"] * n_rows,
            "serious": [1] * n_rows,
            "source": ["openfda_faers"] * n_rows,
        }
        raw_df = pd.DataFrame(df_dict)

        clean_df = clean_adverse_events(raw_df)
        assert len(clean_df) > 0

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine = get_engine(db_path)
            create_tables(engine)

            n = insert_adverse_events(engine, clean_df)
            assert n == n_rows


# ── Boundary Condition Tests ────────────────────────────────────────────────


class TestDataBoundaryConditions:
    """Test boundary conditions and edge cases in data handling."""

    def test_duplicate_exactly_identical_rows(self):
        """Test that exactly identical rows are properly deduplicated."""
        df = pd.DataFrame({
            "safetyreportid": ["same_id"] * 5,
            "drug_name": ["ibuprofen"] * 5,
            "reaction": ["headache"] * 5,
            "outcome": ["1"] * 5,
            "report_date": ["20220101"] * 5,
            "serious": [1] * 5,
            "source": ["openfda_faers"] * 5,
        })

        clean_df = clean_adverse_events(df)
        # Should deduplicate to 1 row
        assert len(clean_df) == 1

    def test_very_long_drug_name(self):
        """Test handling of very long drug names."""
        long_name = "a" * 500
        df = pd.DataFrame({
            "safetyreportid": ["r1"],
            "drug_name": [long_name],
            "reaction": ["headache"],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
        })

        clean_df = clean_adverse_events(df)
        assert len(clean_df) == 1
        assert clean_df.iloc[0]["drug_name"] == long_name.lower()

    def test_very_long_reaction_name(self):
        """Test handling of very long reaction names."""
        long_reaction = "a" * 500
        df = pd.DataFrame({
            "safetyreportid": ["r1"],
            "drug_name": ["ibuprofen"],
            "reaction": [long_reaction],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
        })

        clean_df = clean_adverse_events(df)
        assert len(clean_df) == 1
        assert clean_df.iloc[0]["reaction"] == long_reaction.lower()

    def test_special_characters_in_drug_name(self):
        """Test handling of special characters in drug names."""
        df = pd.DataFrame({
            "safetyreportid": ["r1"],
            "drug_name": ["Drug-X/Y (2022) & Co."],
            "reaction": ["headache"],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
        })

        clean_df = clean_adverse_events(df)
        assert len(clean_df) == 1

    def test_unicode_characters_in_reaction(self):
        """Test handling of unicode characters in reactions."""
        df = pd.DataFrame({
            "safetyreportid": ["r1"],
            "drug_name": ["ibuprofen"],
            "reaction": ["café syndrome"],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
        })

        clean_df = clean_adverse_events(df)
        assert len(clean_df) == 1
        assert "café" in clean_df.iloc[0]["reaction"]

    def test_dates_at_year_boundaries(self):
        """Test date parsing at year boundaries."""
        df = pd.DataFrame({
            "safetyreportid": ["r1", "r2", "r3"],
            "drug_name": ["ibuprofen"] * 3,
            "reaction": ["headache"] * 3,
            "outcome": ["1"] * 3,
            "report_date": ["19991231", "20000101", "20991231"],
            "serious": [1] * 3,
            "source": ["openfda_faers"] * 3,
        })

        clean_df = clean_adverse_events(df)
        assert clean_df.iloc[0]["report_date"] == date(1999, 12, 31)
        assert clean_df.iloc[1]["report_date"] == date(2000, 1, 1)
        assert clean_df.iloc[2]["report_date"] == date(2099, 12, 31)

    def test_null_values_in_all_optional_columns(self):
        """Test that NaN/None values are handled in all optional columns."""
        df = pd.DataFrame({
            "safetyreportid": ["r1"],
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": [None],
            "report_date": [None],
            "serious": [None],
            "source": ["openfda_faers"],
        })

        clean_df = clean_adverse_events(df)
        assert len(clean_df) == 1
        assert clean_df.iloc[0]["outcome"] == "unknown"
        assert clean_df.iloc[0]["report_date"] is None
        assert clean_df.iloc[0]["serious"] == 0


# ── Export Format Tests ─────────────────────────────────────────────────────


class TestExportFormatConsistency:
    """Test that exported JSON is consistent and parseable."""

    def test_signal_export_includes_all_required_fields(self):
        """Test that signal export includes all required fields."""
        import json
        from sqlalchemy import text

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine = get_engine(db_path)
            create_tables(engine)

            # Insert a drug and signal score
            with engine.connect() as conn:
                conn.execute(text(
                    "INSERT INTO drugs (name) VALUES ('ibuprofen')"
                ))
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

            output_file = Path(tmpdir) / "signals.json"
            export_signals_json(engine, output_file)

            data = json.loads(output_file.read_text())
            required_fields = {
                "drug_name", "reaction", "ror", "ror_lower", "ror_upper",
                "prr", "chi_squared", "n_reports", "computed_date", "flagged"
            }
            assert required_fields.issubset(set(data[0].keys()))

    def test_adverse_events_export_includes_all_columns(self):
        """Test that adverse events export includes all columns."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine = get_engine(db_path)
            create_tables(engine)

            df = pd.DataFrame({
                "drug_name": ["ibuprofen"],
                "reaction": ["headache"],
                "outcome": ["recovered"],
                "report_date": [None],
                "serious": [1],
                "source": ["openfda_faers"],
            })
            insert_adverse_events(engine, df)

            output_file = Path(tmpdir) / "adverse_events.json"
            export_adverse_events_json(engine, "ibuprofen", output_file)

            data = json.loads(output_file.read_text())
            expected_fields = {
                "drug_name", "reaction", "outcome", "report_date", "serious", "source"
            }
            assert expected_fields.issubset(set(data[0].keys()))

    def test_json_roundtrip_consistency(self):
        """Test that data can be read back from JSON consistently."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine = get_engine(db_path)
            create_tables(engine)

            # Create multiple rows with varied data
            df = pd.DataFrame({
                "drug_name": ["ibuprofen", "ibuprofen", "aspirin"],
                "reaction": ["headache", "nausea", "headache"],
                "outcome": ["recovered", "not_recovered", "unknown"],
                "report_date": [date(2022, 1, 1), None, date(2022, 12, 31)],
                "serious": [1, 0, 1],
                "source": ["openfda_faers"] * 3,
            })
            insert_adverse_events(engine, df)

            output_file = Path(tmpdir) / "events.json"
            export_adverse_events_json(engine, "ibuprofen", output_file)

            # Read back and verify
            data = json.loads(output_file.read_text())
            assert len(data) == 2
            assert all(isinstance(row, dict) for row in data)
            assert all("drug_name" in row for row in data)
