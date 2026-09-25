"""Tests for pipeline.ingest — OpenFDA fetch, sort order and retry policy."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from pipeline import ingest, run_refresh
from pipeline.ingest import (
    FetchTimeoutError,
    RateLimitExceededError,
    _fetch_page,
    fetch_adverse_events,
)

REPORT = {
    "safetyreportid": "1",
    "receivedate": "20260901",
    "serious": "1",
    "patient": {"reaction": [{"reactionmeddrapt": "Nausea", "reactionoutcome": "1"}]},
}


def _ok(results: list[dict]) -> MagicMock:
    resp = MagicMock(status_code=200, ok=True)
    resp.json.return_value = {"results": results}
    return resp


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest.time, "sleep", lambda _s: None)


class TestFetchPage:
    @patch("pipeline.ingest.requests.get")
    def test_requests_newest_first(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _ok([REPORT])
        _fetch_page("aspirin", 0, 10, "")
        assert mock_get.call_args.kwargs["params"]["sort"] == "receivedate:desc"

    @patch("pipeline.ingest.requests.get")
    def test_timeout_is_retried(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = [requests.Timeout(), _ok([REPORT])]
        rows = _fetch_page("ibuprofen", 0, 10, "")
        assert mock_get.call_count == 2
        assert rows[0]["reaction"] == "Nausea"

    @patch("pipeline.ingest.requests.get")
    def test_persistent_timeout_raises(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = requests.Timeout()
        with pytest.raises(FetchTimeoutError):
            _fetch_page("ibuprofen", 0, 10, "")
        assert mock_get.call_count == 1 + len(ingest._RETRY_DELAYS)

    @patch("pipeline.ingest.requests.get")
    def test_persistent_429_raises(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=429, ok=False)
        with pytest.raises(RateLimitExceededError):
            _fetch_page("aspirin", 0, 10, "")

    @patch("pipeline.ingest.requests.get")
    def test_timeout_then_429_exhaustion_raises_rate_limit(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = [requests.Timeout()] + [MagicMock(status_code=429, ok=False)] * 3
        with pytest.raises(RateLimitExceededError):
            _fetch_page("aspirin", 0, 10, "")


class TestFetchAdverseEvents:
    @patch("pipeline.ingest.requests.get")
    def test_timeout_propagates(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = requests.Timeout()
        with pytest.raises(FetchTimeoutError):
            fetch_adverse_events("ibuprofen", max_records=10)


class TestRunRefreshFailsLoudly:
    def test_missing_drug_aborts_before_signals(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(run_refresh, "get_engine", MagicMock())
        monkeypatch.setattr(run_refresh, "create_tables", MagicMock())
        monkeypatch.setattr(run_refresh, "seed_drug_aliases", MagicMock())
        monkeypatch.setattr(run_refresh, "clear_adverse_events", MagicMock())
        monkeypatch.setattr(run_refresh, "insert_adverse_events", MagicMock(return_value=1))
        monkeypatch.setattr(run_refresh, "clean_adverse_events", lambda df: df)
        compute = MagicMock()
        monkeypatch.setattr(run_refresh, "compute_all_signals", compute)
        monkeypatch.setattr(run_refresh, "DRUG_LIST", ["ibuprofen", "aspirin"])

        def fake_fetch(drug: str, max_records: int) -> pd.DataFrame:
            return ingest._empty_frame() if drug == "ibuprofen" else pd.DataFrame([{"x": 1}])

        monkeypatch.setattr(run_refresh, "fetch_adverse_events", fake_fetch)

        assert run_refresh.main() == 1
        compute.assert_not_called()
