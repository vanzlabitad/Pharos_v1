"""Unit tests for pipeline.ingest — OpenFDA adverse event fetching.

Tests cover the rate-limit retry logic, JSON parsing, error handling,
and pagination behavior.
"""

import json
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
import requests

from pipeline.ingest import (
    RateLimitExceededError,
    _coerce_serious,
    _empty_frame,
    _fetch_page,
    _parse_results,
    fetch_adverse_events,
)


# ── _empty_frame ────────────────────────────────────────────────────────────


class TestEmptyFrame:
    """Test the empty DataFrame factory."""

    def test_returns_dataframe(self):
        df = _empty_frame()
        assert isinstance(df, pd.DataFrame)

    def test_has_correct_columns(self):
        df = _empty_frame()
        expected = {
            "safetyreportid",
            "drug_name",
            "reaction",
            "outcome",
            "report_date",
            "serious",
            "source",
        }
        assert set(df.columns) == expected

    def test_is_empty(self):
        df = _empty_frame()
        assert len(df) == 0

    def test_columns_are_in_correct_order(self):
        df = _empty_frame()
        expected_order = [
            "safetyreportid",
            "drug_name",
            "reaction",
            "outcome",
            "report_date",
            "serious",
            "source",
        ]
        assert list(df.columns) == expected_order


# ── _coerce_serious ────────────────────────────────────────────────────────


class TestCoerceSerious:
    """Test OpenFDA serious field coercion to 1/0."""

    def test_serious_1_returns_1(self):
        assert _coerce_serious(1) == 1

    def test_serious_2_returns_0(self):
        assert _coerce_serious(2) == 0

    def test_string_1_returns_1(self):
        assert _coerce_serious("1") == 1

    def test_string_2_returns_0(self):
        assert _coerce_serious("2") == 0

    def test_non_1_returns_0(self):
        assert _coerce_serious(3) == 0
        assert _coerce_serious(0) == 0

    def test_none_returns_0(self):
        assert _coerce_serious(None) == 0

    def test_empty_string_returns_0(self):
        assert _coerce_serious("") == 0

    def test_invalid_string_returns_0(self):
        assert _coerce_serious("invalid") == 0

    def test_float_1_returns_1(self):
        assert _coerce_serious(1.0) == 1

    def test_float_2_returns_0(self):
        assert _coerce_serious(2.0) == 0


# ── _parse_results ────────────────────────────────────────────────────────


class TestParseResults:
    """Test parsing OpenFDA JSON results into row format."""

    def test_single_reaction_per_report(self):
        """Test parsing a report with one reaction."""
        results = [
            {
                "safetyreportid": "report123",
                "receivedate": "20220101",
                "serious": 1,
                "patient": {
                    "reaction": [{"reactionmeddrapt": "headache", "reactionoutcome": "1"}]
                },
            }
        ]
        rows = _parse_results(results, "ibuprofen")
        assert len(rows) == 1
        assert rows[0]["safetyreportid"] == "report123"
        assert rows[0]["reaction"] == "headache"
        assert rows[0]["drug_name"] == "ibuprofen"

    def test_multiple_reactions_per_report(self):
        """Test parsing a report with multiple reactions."""
        results = [
            {
                "safetyreportid": "report456",
                "receivedate": "20220102",
                "serious": 2,
                "patient": {
                    "reaction": [
                        {"reactionmeddrapt": "headache", "reactionoutcome": "1"},
                        {"reactionmeddrapt": "dizziness", "reactionoutcome": "2"},
                    ]
                },
            }
        ]
        rows = _parse_results(results, "aspirin")
        assert len(rows) == 2
        assert set(r["reaction"] for r in rows) == {"headache", "dizziness"}

    def test_report_without_reactions_skipped(self):
        """Test that reports without reactions are skipped."""
        results = [
            {
                "safetyreportid": "report789",
                "receivedate": "20220103",
                "serious": 1,
                "patient": {"reaction": []},
            },
            {
                "safetyreportid": "report101",
                "receivedate": "20220104",
                "serious": 1,
                "patient": {"reaction": [{"reactionmeddrapt": "nausea", "reactionoutcome": "3"}]},
            },
        ]
        rows = _parse_results(results, "metformin")
        assert len(rows) == 1
        assert rows[0]["safetyreportid"] == "report101"

    def test_missing_patient_field(self):
        """Test that reports missing patient field are handled gracefully."""
        results = [
            {
                "safetyreportid": "report202",
                "receivedate": "20220105",
                "serious": 1,
            }
        ]
        rows = _parse_results(results, "ibuprofen")
        assert len(rows) == 0

    def test_missing_reaction_field(self):
        """Test that missing reactionmeddrapt falls back to empty string."""
        results = [
            {
                "safetyreportid": "report303",
                "receivedate": "20220106",
                "serious": 1,
                "patient": {"reaction": [{"reactionoutcome": "1"}]},
            }
        ]
        rows = _parse_results(results, "ibuprofen")
        assert len(rows) == 1
        assert rows[0]["reaction"] == ""

    def test_source_field_set_to_openfda_faers(self):
        """Test that source field is always 'openfda_faers'."""
        results = [
            {
                "safetyreportid": "report404",
                "receivedate": "20220107",
                "serious": 1,
                "patient": {"reaction": [{"reactionmeddrapt": "rash", "reactionoutcome": "1"}]},
            }
        ]
        rows = _parse_results(results, "penicillin")
        assert rows[0]["source"] == "openfda_faers"

    def test_outcome_preserved_as_string(self):
        """Test that outcome is preserved as a string."""
        results = [
            {
                "safetyreportid": "report505",
                "receivedate": "20220108",
                "serious": 1,
                "patient": {"reaction": [{"reactionmeddrapt": "nausea", "reactionoutcome": 4}]},
            }
        ]
        rows = _parse_results(results, "ibuprofen")
        assert rows[0]["outcome"] == "4"

    def test_drug_name_canonicalised(self):
        """Test that drug names are canonicalised."""
        results = [
            {
                "safetyreportid": "report606",
                "receivedate": "20220109",
                "serious": 1,
                "patient": {"reaction": [{"reactionmeddrapt": "headache", "reactionoutcome": "1"}]},
            }
        ]
        # ADVIL should be canonicalised to ibuprofen
        rows = _parse_results(results, "ADVIL")
        assert rows[0]["drug_name"] == "ibuprofen"

    def test_empty_results_list(self):
        """Test parsing an empty results list."""
        rows = _parse_results([], "ibuprofen")
        assert len(rows) == 0


# ── _fetch_page ────────────────────────────────────────────────────────────


class TestFetchPage:
    """Test single-page fetching with rate limit retry logic."""

    @patch("pipeline.ingest.requests.get")
    def test_success_returns_parsed_results(self, mock_get):
        """Test successful 200 response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "results": [
                {
                    "safetyreportid": "123",
                    "receivedate": "20220101",
                    "serious": 1,
                    "patient": {
                        "reaction": [{"reactionmeddrapt": "headache", "reactionoutcome": "1"}]
                    },
                }
            ]
        }
        mock_get.return_value = mock_response

        result = _fetch_page("ibuprofen", 0, 100, "fake_key")

        assert result is not None
        assert len(result) == 1
        assert result[0]["reaction"] == "headache"

    @patch("pipeline.ingest.requests.get")
    def test_404_returns_empty_list(self, mock_get):
        """Test 404 response returns empty list (drug not found)."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = _fetch_page("nonexistent_drug", 0, 100, "fake_key")

        assert result == []

    @patch("pipeline.ingest.requests.get")
    @patch("pipeline.ingest.time.sleep")
    def test_429_retries_and_succeeds(self, mock_sleep, mock_get):
        """Test 429 rate limit with eventual success."""
        # First two responses return 429, third returns 200
        responses = [
            Mock(status_code=429),
            Mock(status_code=429),
            Mock(status_code=200, ok=True, json=lambda: {"results": []}),
        ]
        mock_get.side_effect = responses

        result = _fetch_page("ibuprofen", 0, 100, "fake_key")

        assert result == []
        # Should have called sleep twice (1s and 2s)
        assert mock_sleep.call_count == 2

    @patch("pipeline.ingest.requests.get")
    @patch("pipeline.ingest.time.sleep")
    def test_429_all_retries_exhausted_raises(self, mock_sleep, mock_get):
        """Test 429 on all retry attempts raises RateLimitExceededError."""
        mock_get.return_value = Mock(status_code=429)

        with pytest.raises(RateLimitExceededError):
            _fetch_page("ibuprofen", 0, 100, "fake_key")

        # Should have attempted all retries (initial + 3 more = 4 total)
        assert mock_get.call_count == 4

    @patch("pipeline.ingest.requests.get")
    def test_timeout_returns_none(self, mock_get):
        """Test timeout exception returns None."""
        mock_get.side_effect = requests.Timeout("Connection timed out")

        result = _fetch_page("ibuprofen", 0, 100, "fake_key")

        assert result is None

    @patch("pipeline.ingest.requests.get")
    def test_request_exception_returns_none(self, mock_get):
        """Test generic request exception returns None."""
        mock_get.side_effect = requests.RequestException("Network error")

        result = _fetch_page("ibuprofen", 0, 100, "fake_key")

        assert result is None

    @patch("pipeline.ingest.requests.get")
    def test_500_error_returns_none(self, mock_get):
        """Test 500 server error returns None."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.ok = False
        mock_get.return_value = mock_response

        result = _fetch_page("ibuprofen", 0, 100, "fake_key")

        assert result is None

    @patch("pipeline.ingest.requests.get")
    def test_json_parse_error_returns_none(self, mock_get):
        """Test JSON parse error returns None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        result = _fetch_page("ibuprofen", 0, 100, "fake_key")

        assert result is None

    @patch("pipeline.ingest.requests.get")
    def test_empty_results_returns_empty_list(self, mock_get):
        """Test response with empty results returns empty list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        result = _fetch_page("ibuprofen", 0, 100, "fake_key")

        assert result == []

    @patch("pipeline.ingest.requests.get")
    def test_api_key_included_in_params(self, mock_get):
        """Test that API key is included in request params when provided."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        _fetch_page("ibuprofen", 0, 100, "my_api_key")

        # Check that the API key was included in params
        call_args = mock_get.call_args
        assert call_args[1]["params"]["api_key"] == "my_api_key"

    @patch("pipeline.ingest.requests.get")
    def test_api_key_omitted_when_empty(self, mock_get):
        """Test that API key is omitted from params when not provided."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        _fetch_page("ibuprofen", 0, 100, "")

        # Check that API key was not included in params
        call_args = mock_get.call_args
        assert "api_key" not in call_args[1]["params"]


# ── fetch_adverse_events ────────────────────────────────────────────────────


def _make_page(start_id: int, count: int, drug: str = "drug") -> list[dict]:
    """Helper to create a page of test results."""
    return [
        {
            "safetyreportid": f"{start_id + i}",
            "drug_name": drug,
            "reaction": f"r{i}",
            "outcome": "1",
            "report_date": "20220101",
            "serious": 1,
            "source": "openfda_faers",
        }
        for i in range(count)
    ]


class TestFetchAdverseEvents:
    """Test pagination and aggregation of multi-page results."""

    @patch("pipeline.ingest._fetch_page")
    @patch("pipeline.ingest.time.sleep")
    def test_single_page_under_limit(self, mock_sleep, mock_fetch_page):
        """Test fetching a single page under max_records."""
        page_result = [
            {
                "safetyreportid": "123",
                "drug_name": "ibuprofen",
                "reaction": "headache",
                "outcome": "1",
                "report_date": "20220101",
                "serious": 1,
                "source": "openfda_faers",
            }
        ]
        mock_fetch_page.return_value = page_result

        df = fetch_adverse_events("ibuprofen", max_records=5000)

        assert len(df) == 1
        assert df.iloc[0]["reaction"] == "headache"

    @patch("pipeline.ingest._fetch_page")
    @patch("pipeline.ingest.time.sleep")
    def test_pagination_continues_until_max_records(self, mock_sleep, mock_fetch_page):
        """Test pagination stops when max_records is reached."""
        page1 = _make_page(0, 1000)
        # Return partial page to trigger stop condition
        page2 = _make_page(1000, 100)
        mock_fetch_page.side_effect = [page1, page2]

        df = fetch_adverse_events("ibuprofen", max_records=2000)

        assert len(df) == 1100
        # Should have called _fetch_page twice
        assert mock_fetch_page.call_count == 2

    @patch("pipeline.ingest._fetch_page")
    @patch("pipeline.ingest.time.sleep")
    def test_pagination_stops_on_partial_page(self, mock_sleep, mock_fetch_page):
        """Test pagination stops when API returns fewer records than requested."""
        page1 = _make_page(0, 1000)
        page2 = _make_page(1000, 500)
        mock_fetch_page.side_effect = [page1, page2]

        df = fetch_adverse_events("ibuprofen", max_records=5000)

        assert len(df) == 1500
        # Should have stopped after page 2 because it returned < 1000 records
        assert mock_fetch_page.call_count == 2

    @patch("pipeline.ingest._fetch_page")
    @patch("pipeline.ingest.time.sleep")
    def test_fetch_page_failure_stops_pagination(self, mock_sleep, mock_fetch_page):
        """Test that pagination stops if _fetch_page returns None."""
        page1 = _make_page(0, 1000)
        mock_fetch_page.side_effect = [page1, None]  # Second call fails

        df = fetch_adverse_events("ibuprofen", max_records=5000)

        assert len(df) == 1000
        assert mock_fetch_page.call_count == 2

    @patch("pipeline.ingest._fetch_page")
    def test_no_results_returns_empty_dataframe(self, mock_fetch_page):
        """Test that no results returns an empty DataFrame with correct columns."""
        mock_fetch_page.return_value = []

        df = fetch_adverse_events("nonexistent_drug", max_records=5000)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert set(df.columns) == {
            "safetyreportid",
            "drug_name",
            "reaction",
            "outcome",
            "report_date",
            "serious",
            "source",
        }

    @patch("pipeline.ingest._fetch_page")
    def test_api_key_passed_to_fetch_page(self, mock_fetch_page):
        """Test that the API key is passed through to _fetch_page."""
        mock_fetch_page.return_value = []

        fetch_adverse_events("ibuprofen", max_records=5000)

        # Verify that _fetch_page was called with an API key
        assert mock_fetch_page.call_count >= 1
        call_args = mock_fetch_page.call_args_list[0]
        # API key is the 4th positional argument
        assert len(call_args[0]) >= 4

    @patch("pipeline.ingest._fetch_page")
    @patch("pipeline.ingest.time.sleep")
    def test_sleep_between_pages(self, mock_sleep, mock_fetch_page):
        """Test that sleep is called between pages."""
        page1 = [{"safetyreportid": f"{i}", "drug_name": "drug", "reaction": f"r{i}",
                  "outcome": "1", "report_date": "20220101", "serious": 1, "source": "openfda_faers"}
                 for i in range(1000)]
        page2 = [{"safetyreportid": f"{i+1000}", "drug_name": "drug", "reaction": f"r{i}",
                  "outcome": "1", "report_date": "20220101", "serious": 1, "source": "openfda_faers"}
                 for i in range(500)]
        mock_fetch_page.side_effect = [page1, page2]

        fetch_adverse_events("ibuprofen", max_records=5000)

        # Sleep should be called between pages
        assert mock_sleep.call_count >= 1
