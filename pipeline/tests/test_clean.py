"""Unit tests for pipeline.clean — adverse events normalisation and deduplication.

Tests cover outcome mapping, date parsing, deduplication, and the full
cleaning pipeline.
"""

from datetime import date

import pandas as pd
import pytest

from pipeline.clean import clean_adverse_events, _parse_date


# ── _parse_date ─────────────────────────────────────────────────────────────


class TestParseDate:
    """Test YYYYMMDD date string parsing."""

    def test_valid_date_string(self):
        """Test parsing a valid YYYYMMDD string."""
        assert _parse_date("20220315") == date(2022, 3, 15)

    def test_valid_date_string_jan_1(self):
        """Test parsing Jan 1."""
        assert _parse_date("20220101") == date(2022, 1, 1)

    def test_valid_date_string_dec_31(self):
        """Test parsing Dec 31."""
        assert _parse_date("20221231") == date(2022, 12, 31)

    def test_leap_year_feb_29(self):
        """Test parsing Feb 29 in a leap year."""
        assert _parse_date("20200229") == date(2020, 2, 29)

    def test_invalid_month_returns_none(self):
        """Test that invalid month returns None."""
        assert _parse_date("20221301") is None

    def test_invalid_day_returns_none(self):
        """Test that invalid day returns None."""
        assert _parse_date("20220230") is None

    def test_feb_29_non_leap_year_returns_none(self):
        """Test that Feb 29 in non-leap year returns None."""
        assert _parse_date("20210229") is None

    def test_empty_string_returns_none(self):
        """Test that empty string returns None."""
        assert _parse_date("") is None

    def test_whitespace_only_returns_none(self):
        """Test that whitespace-only string returns None."""
        assert _parse_date("   ") is None

    def test_none_returns_none(self):
        """Test that None input returns None."""
        assert _parse_date(None) is None

    def test_string_with_whitespace_is_stripped(self):
        """Test that whitespace is stripped before parsing."""
        assert _parse_date("  20220315  ") == date(2022, 3, 15)

    def test_integer_input_converted_to_string(self):
        """Test that integer input is converted to string."""
        assert _parse_date(20220315) == date(2022, 3, 15)

    def test_too_short_string_returns_none(self):
        """Test that very short strings (< 8 chars) return None."""
        # 6-digit string is too short for YYYYMMDD format
        assert _parse_date("202203") is None

    def test_non_numeric_string_returns_none(self):
        """Test that non-numeric string returns None."""
        assert _parse_date("abcdefgh") is None

    def test_year_zero_returns_none(self):
        """Test that year 0 returns None."""
        assert _parse_date("00000101") is None


# ── clean_adverse_events ────────────────────────────────────────────────────


class TestCleanAdverseEvents:
    """Test the full cleaning pipeline."""

    def test_empty_dataframe_returns_empty_with_schema_columns(self):
        """Test that empty input returns empty DataFrame with schema columns."""
        df = pd.DataFrame()
        result = clean_adverse_events(df)
        expected_cols = {"drug_name", "reaction", "outcome", "report_date", "serious", "source"}
        assert set(result.columns) == expected_cols
        assert len(result) == 0

    def test_drops_null_reaction(self):
        """Test that rows with null reaction are dropped."""
        df = pd.DataFrame({
            "safetyreportid": ["1", "2"],
            "drug_name": ["ibuprofen", "ibuprofen"],
            "reaction": ["headache", None],
            "outcome": ["1", "1"],
            "report_date": ["20220101", "20220102"],
            "serious": [1, 1],
            "source": ["openfda_faers", "openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert len(result) == 1
        assert result.iloc[0]["reaction"] == "headache"

    def test_drops_empty_reaction(self):
        """Test that rows with empty string reaction are dropped."""
        df = pd.DataFrame({
            "safetyreportid": ["1", "2"],
            "drug_name": ["ibuprofen", "ibuprofen"],
            "reaction": ["headache", "   "],
            "outcome": ["1", "1"],
            "report_date": ["20220101", "20220102"],
            "serious": [1, 1],
            "source": ["openfda_faers", "openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert len(result) == 1

    def test_canonicalises_drug_name(self):
        """Test that drug names are canonicalised."""
        df = pd.DataFrame({
            "safetyreportid": ["1"],
            "drug_name": ["ADVIL"],
            "reaction": ["headache"],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        result = clean_adverse_events(df)
        # ADVIL should be canonicalised to ibuprofen
        assert result.iloc[0]["drug_name"] == "ibuprofen"

    def test_lowercases_reaction(self):
        """Test that reactions are lowercased."""
        df = pd.DataFrame({
            "safetyreportid": ["1"],
            "drug_name": ["ibuprofen"],
            "reaction": ["HEADACHE"],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert result.iloc[0]["reaction"] == "headache"

    def test_strips_reaction_whitespace(self):
        """Test that reaction whitespace is stripped."""
        df = pd.DataFrame({
            "safetyreportid": ["1"],
            "drug_name": ["ibuprofen"],
            "reaction": ["  headache  "],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert result.iloc[0]["reaction"] == "headache"

    def test_maps_outcome_codes(self):
        """Test that outcome codes are mapped to human-readable strings."""
        df = pd.DataFrame({
            "safetyreportid": ["1", "2", "3", "4", "5", "6"],
            "drug_name": ["drug"] * 6,
            "reaction": ["rxn"] * 6,
            "outcome": ["1", "2", "3", "4", "5", "6"],
            "report_date": ["20220101"] * 6,
            "serious": [1] * 6,
            "source": ["openfda_faers"] * 6,
        })
        result = clean_adverse_events(df)
        outcomes = result["outcome"].tolist()
        assert outcomes == ["recovered", "recovering", "not_recovered", "fatal", "unknown", "unknown"]

    def test_outcome_numeric_strings_are_mapped(self):
        """Test that numeric string outcomes are mapped."""
        df = pd.DataFrame({
            "safetyreportid": ["1"],
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": [1],  # numeric, not string
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert result.iloc[0]["outcome"] == "recovered"

    def test_parses_report_date(self):
        """Test that report_date is parsed from YYYYMMDD to date."""
        df = pd.DataFrame({
            "safetyreportid": ["1"],
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["1"],
            "report_date": ["20220315"],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert result.iloc[0]["report_date"] == date(2022, 3, 15)

    def test_invalid_date_becomes_none(self):
        """Test that invalid dates become None."""
        df = pd.DataFrame({
            "safetyreportid": ["1"],
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["1"],
            "report_date": ["20220230"],  # Invalid date
            "serious": [1],
            "source": ["openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert result.iloc[0]["report_date"] is None

    def test_coerces_serious_to_int(self):
        """Test that serious field is coerced to int."""
        df = pd.DataFrame({
            "safetyreportid": ["1", "2"],
            "drug_name": ["ibuprofen", "ibuprofen"],
            "reaction": ["headache", "headache"],
            "outcome": ["1", "1"],
            "report_date": ["20220101", "20220102"],
            "serious": ["1", "0"],
            "source": ["openfda_faers", "openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert result.iloc[0]["serious"] == 1
        assert result.iloc[1]["serious"] == 0
        assert result["serious"].dtype in [int, "int64"]

    def test_fills_missing_serious_with_zero(self):
        """Test that missing serious values are filled with 0."""
        df = pd.DataFrame({
            "safetyreportid": ["1"],
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [None],
            "source": ["openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert result.iloc[0]["serious"] == 0

    def test_deduplicates_by_safetyreportid_reaction(self):
        """Test deduplication by safetyreportid + reaction."""
        df = pd.DataFrame({
            "safetyreportid": ["report1", "report1"],
            "drug_name": ["ibuprofen", "ibuprofen"],
            "reaction": ["headache", "headache"],
            "outcome": ["1", "1"],
            "report_date": ["20220101", "20220101"],
            "serious": [1, 1],
            "source": ["openfda_faers", "openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert len(result) == 1

    def test_deduplicates_by_drug_reaction_date_source_when_no_reportid(self):
        """Test deduplication by drug+reaction+date+source when safetyreportid is missing."""
        df = pd.DataFrame({
            "drug_name": ["ibuprofen", "ibuprofen"],
            "reaction": ["headache", "headache"],
            "outcome": ["1", "1"],
            "report_date": ["20220101", "20220101"],
            "serious": [1, 1],
            "source": ["openfda_faers", "openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert len(result) == 1

    def test_drops_safetyreportid_column(self):
        """Test that safetyreportid column is dropped."""
        df = pd.DataFrame({
            "safetyreportid": ["123"],
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
        })
        result = clean_adverse_events(df)
        assert "safetyreportid" not in result.columns

    def test_returns_only_schema_columns_in_order(self):
        """Test that only schema columns are returned in correct order."""
        df = pd.DataFrame({
            "safetyreportid": ["123"],
            "drug_name": ["ibuprofen"],
            "reaction": ["headache"],
            "outcome": ["1"],
            "report_date": ["20220101"],
            "serious": [1],
            "source": ["openfda_faers"],
            "extra_column": ["should be dropped"],
        })
        result = clean_adverse_events(df)
        expected_cols = ["drug_name", "reaction", "outcome", "report_date", "serious", "source"]
        assert list(result.columns) == expected_cols

    def test_reset_index(self):
        """Test that index is reset."""
        df = pd.DataFrame({
            "safetyreportid": ["1", "2"],
            "drug_name": ["ibuprofen", "ibuprofen"],
            "reaction": ["headache", "dizziness"],
            "outcome": ["1", "1"],
            "report_date": ["20220101", "20220102"],
            "serious": [1, 1],
            "source": ["openfda_faers", "openfda_faers"],
        }, index=[10, 20])
        result = clean_adverse_events(df)
        assert list(result.index) == [0, 1]

    def test_full_pipeline_integration(self):
        """Test the complete cleaning pipeline on a realistic dataset."""
        df = pd.DataFrame({
            "safetyreportid": ["r1", "r2", "r3", "r1", "r4"],
            "drug_name": ["ADVIL", "Ibuprofen", "aspirin", "ADVIL", "ibuprofen"],
            "reaction": ["HEADACHE", "  dizziness  ", None, "HEADACHE", "nausea"],
            "outcome": ["1", "2", "3", "1", "4"],
            "report_date": ["20220101", "20220102", "20220103", "20220101", "20220104"],
            "serious": [1, None, 2, 1, "0"],
            "source": ["openfda_faers"] * 5,
        })
        result = clean_adverse_events(df)
        # Should have:
        # - Dropped row with None reaction
        # - Deduplicated (r1 + headache appears twice)
        # - Result should be 3 rows: r1/headache, r2/dizziness, r4/nausea
        assert len(result) == 3
        assert all(result["drug_name"] == "ibuprofen") or result["drug_name"].isin(["ibuprofen", "aspirin"]).all()
        assert set(result["reaction"]) == {"headache", "dizziness", "nausea"}
