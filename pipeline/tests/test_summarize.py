"""Tests for pipeline.summarize — AI summary generation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.summarize import (
    _build_prompt,
    _build_reaction_prompt,
    _drug_is_complete,
    _get_top_flagged_signal,
    _get_top_flagged_signals,
    _load_existing_summaries,
    export_summaries_json,
    generate_summaries,
)

SAMPLE_SIGNALS = [
    {
        "drug_name": "aspirin",
        "reaction": "gi bleeding",
        "ror": 4.2,
        "ror_lower": 3.8,
        "ror_upper": 4.6,
        "prr": 3.5,
        "chi_squared": 12.0,
        "n_reports": 120,
        "flagged": True,
    },
    {
        "drug_name": "aspirin",
        "reaction": "headache",
        "ror": 1.1,
        "ror_lower": 0.9,
        "ror_upper": 1.3,
        "prr": 1.0,
        "chi_squared": 0.5,
        "n_reports": 50,
        "flagged": False,
    },
    {
        "drug_name": "aspirin",
        "reaction": "erosive oesophagitis",
        "ror": 140.0,
        "ror_lower": 8.6,
        "ror_upper": 2284.7,
        "prr": 140.0,
        "chi_squared": 68.2,
        "n_reports": 39,
        "flagged": True,
    },
    {
        "drug_name": "ibuprofen",
        "reaction": "nausea",
        "ror": 0.8,
        "ror_lower": 0.6,
        "ror_upper": 1.0,
        "prr": 0.7,
        "chi_squared": 1.2,
        "n_reports": 30,
        "flagged": False,
    },
]


class TestBuildPrompt:
    def test_contains_drug_name(self) -> None:
        prompt = _build_prompt("ibuprofen", "nausea", 4.2, 3.8, 4.6, 100, True)
        assert "ibuprofen" in prompt

    def test_contains_constraints(self) -> None:
        prompt = _build_prompt("aspirin", "gi bleeding", 4.2, 3.8, 4.6, 100, True)
        assert "Do not give medical advice" in prompt
        assert "Do not use jargon" in prompt

    def test_formats_numbers(self) -> None:
        prompt = _build_prompt("aspirin", "gi bleeding", 4.2, 3.8, 4.6, 100, True)
        assert "4.20" in prompt
        assert "3.80" in prompt
        assert "4.60" in prompt

    def test_flagged_yes(self) -> None:
        prompt = _build_prompt("aspirin", "gi bleeding", 4.2, 3.8, 4.6, 100, True)
        assert "Signal flagged: Yes" in prompt

    def test_flagged_no(self) -> None:
        prompt = _build_prompt("aspirin", "gi bleeding", 1.0, 0.8, 1.2, 5, False)
        assert "Signal flagged: No" in prompt


class TestBuildReactionPrompt:
    def test_contains_drug_and_reaction(self) -> None:
        prompt = _build_reaction_prompt("aspirin", "gi bleeding", 4.2, 3.8, 4.6, 100)
        assert "aspirin" in prompt
        assert "gi bleeding" in prompt

    def test_contains_constraints(self) -> None:
        prompt = _build_reaction_prompt("aspirin", "gi bleeding", 4.2, 3.8, 4.6, 100)
        assert "Do not give medical advice" in prompt

    def test_formats_numbers(self) -> None:
        prompt = _build_reaction_prompt("aspirin", "gi bleeding", 4.2, 3.8, 4.6, 100)
        assert "4.20" in prompt
        assert "3.80" in prompt
        assert "4.60" in prompt


class TestGetTopFlaggedSignal:
    def test_returns_highest_ror(self) -> None:
        top = _get_top_flagged_signal(SAMPLE_SIGNALS, "aspirin")
        assert top is not None
        assert top["reaction"] == "erosive oesophagitis"
        assert top["ror"] == 140.0

    def test_returns_none_when_unflagged(self) -> None:
        top = _get_top_flagged_signal(SAMPLE_SIGNALS, "ibuprofen")
        assert top is None

    def test_returns_none_for_missing_drug(self) -> None:
        top = _get_top_flagged_signal(SAMPLE_SIGNALS, "metformin")
        assert top is None


class TestGetTopFlaggedSignals:
    def test_returns_sorted_list(self) -> None:
        results = _get_top_flagged_signals(SAMPLE_SIGNALS, "aspirin")
        assert len(results) == 2
        assert results[0]["ror"] >= results[1]["ror"]
        assert results[0]["reaction"] == "erosive oesophagitis"

    def test_respects_limit(self) -> None:
        results = _get_top_flagged_signals(SAMPLE_SIGNALS, "aspirin", limit=1)
        assert len(results) == 1
        assert results[0]["reaction"] == "erosive oesophagitis"

    def test_returns_empty_when_unflagged(self) -> None:
        results = _get_top_flagged_signals(SAMPLE_SIGNALS, "ibuprofen")
        assert results == []

    def test_returns_empty_for_missing_drug(self) -> None:
        results = _get_top_flagged_signals(SAMPLE_SIGNALS, "metformin")
        assert results == []


class TestExportSummariesJson:
    def test_writes_file(self, tmp_path: Path) -> None:
        out = tmp_path / "summaries.json"
        summaries = {
            "aspirin": {
                "overall": "Test summary for aspirin.",
                "reactions": {"gi bleeding": "GI bleeding explanation."},
            }
        }
        n = export_summaries_json(summaries, out)
        assert n == 1
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["aspirin"]["overall"] == "Test summary for aspirin."
        assert data["aspirin"]["reactions"]["gi bleeding"] == "GI bleeding explanation."

    def test_writes_empty_dict(self, tmp_path: Path) -> None:
        out = tmp_path / "summaries.json"
        n = export_summaries_json({}, out)
        assert n == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == {}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipeline.summarize.time.sleep", lambda _: None)


class TestGenerateSummaries:
    def test_skips_without_api_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        signals_path = tmp_path / "signals.json"
        signals_path.write_text(json.dumps(SAMPLE_SIGNALS))
        result = generate_summaries(signals_path)
        assert result == {}

    def test_skips_when_no_flagged_signals(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        unflagged = [s | {"flagged": False} for s in SAMPLE_SIGNALS]
        signals_path = tmp_path / "signals.json"
        signals_path.write_text(json.dumps(unflagged))
        result = generate_summaries(signals_path)
        assert result == {}

    def test_returns_empty_when_file_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        result = generate_summaries(tmp_path / "nonexistent.json")
        assert result == {}

    @patch("pipeline.summarize._call_gemini")
    def test_generates_for_flagged_drugs(
        self, mock_gemini: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        mock_gemini.return_value = "A test summary."
        signals_path = tmp_path / "signals.json"
        signals_path.write_text(json.dumps(SAMPLE_SIGNALS))

        result = generate_summaries(signals_path)

        assert "aspirin" in result
        assert result["aspirin"]["overall"] == "A test summary."
        assert "ibuprofen" not in result

    @patch("pipeline.summarize._call_gemini")
    def test_generates_reaction_summaries(
        self, mock_gemini: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        mock_gemini.return_value = "A test summary."
        signals_path = tmp_path / "signals.json"
        signals_path.write_text(json.dumps(SAMPLE_SIGNALS))

        result = generate_summaries(signals_path)

        assert "aspirin" in result
        reactions = result["aspirin"]["reactions"]
        assert "erosive oesophagitis" in reactions
        assert "gi bleeding" in reactions
        assert reactions["erosive oesophagitis"] == "A test summary."


class TestLoadExistingSummaries:
    def test_returns_empty_for_none(self) -> None:
        assert _load_existing_summaries(None) == {}

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        assert _load_existing_summaries(tmp_path / "nope.json") == {}

    def test_loads_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "summaries.json"
        data = {"aspirin": {"overall": "existing", "reactions": {}}}
        p.write_text(json.dumps(data))
        assert _load_existing_summaries(p) == data

    def test_returns_empty_for_corrupt_json(self, tmp_path: Path) -> None:
        p = tmp_path / "summaries.json"
        p.write_text("not json{{{")
        assert _load_existing_summaries(p) == {}


class TestDrugIsComplete:
    def test_complete_drug(self) -> None:
        existing = {
            "aspirin": {
                "overall": "summary text",
                "reactions": {"gi bleeding": "text", "erosive oesophagitis": "text"},
            }
        }
        assert _drug_is_complete(existing, "aspirin", {"gi bleeding", "erosive oesophagitis"})

    def test_missing_overall(self) -> None:
        existing = {"aspirin": {"overall": "", "reactions": {"gi bleeding": "text"}}}
        assert not _drug_is_complete(existing, "aspirin", {"gi bleeding"})

    def test_missing_reaction(self) -> None:
        existing = {
            "aspirin": {"overall": "text", "reactions": {"gi bleeding": "text"}}
        }
        assert not _drug_is_complete(existing, "aspirin", {"gi bleeding", "new reaction"})

    def test_missing_drug(self) -> None:
        assert not _drug_is_complete({}, "aspirin", {"gi bleeding"})

    def test_non_dict_entry(self) -> None:
        assert not _drug_is_complete({"aspirin": "old string format"}, "aspirin", {"gi bleeding"})


class TestIncrementalGeneration:
    @patch("pipeline.summarize._call_gemini")
    def test_skips_complete_drug(
        self, mock_gemini: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        signals_path = tmp_path / "signals.json"
        signals_path.write_text(json.dumps(SAMPLE_SIGNALS))

        existing_path = tmp_path / "existing.json"
        existing_path.write_text(json.dumps({
            "aspirin": {
                "overall": "Existing aspirin summary.",
                "reactions": {
                    "erosive oesophagitis": "Existing erosive text.",
                    "gi bleeding": "Existing gi text.",
                },
            }
        }))

        result = generate_summaries(signals_path, existing_path=existing_path)

        mock_gemini.assert_not_called()
        assert result["aspirin"]["overall"] == "Existing aspirin summary."
        assert result["aspirin"]["reactions"]["gi bleeding"] == "Existing gi text."

    @patch("pipeline.summarize._call_gemini")
    def test_fills_missing_reactions(
        self, mock_gemini: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        mock_gemini.return_value = "New reaction text."
        signals_path = tmp_path / "signals.json"
        signals_path.write_text(json.dumps(SAMPLE_SIGNALS))

        existing_path = tmp_path / "existing.json"
        existing_path.write_text(json.dumps({
            "aspirin": {
                "overall": "Existing overall.",
                "reactions": {"erosive oesophagitis": "Already done."},
            }
        }))

        result = generate_summaries(signals_path, existing_path=existing_path)

        assert result["aspirin"]["overall"] == "Existing overall."
        assert result["aspirin"]["reactions"]["erosive oesophagitis"] == "Already done."
        assert result["aspirin"]["reactions"]["gi bleeding"] == "New reaction text."
        assert mock_gemini.call_count == 1

    @patch("pipeline.summarize._call_gemini")
    def test_generates_new_drug_fully(
        self, mock_gemini: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        mock_gemini.return_value = "Generated text."
        signals_path = tmp_path / "signals.json"
        signals_path.write_text(json.dumps(SAMPLE_SIGNALS))

        result = generate_summaries(signals_path, existing_path=None)

        assert "aspirin" in result
        assert result["aspirin"]["overall"] == "Generated text."
        assert len(result["aspirin"]["reactions"]) == 2
        # 1 overall + 2 reactions = 3 calls
        assert mock_gemini.call_count == 3

    @patch("pipeline.summarize._call_gemini")
    def test_preserves_existing_drugs_not_in_signals(
        self, mock_gemini: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        mock_gemini.return_value = "New."
        signals_path = tmp_path / "signals.json"
        signals_path.write_text(json.dumps(SAMPLE_SIGNALS))

        existing_path = tmp_path / "existing.json"
        existing_path.write_text(json.dumps({
            "old_drug": {"overall": "Old drug summary.", "reactions": {}},
        }))

        result = generate_summaries(signals_path, existing_path=existing_path)

        assert result["old_drug"]["overall"] == "Old drug summary."
        assert "aspirin" in result

    @patch("pipeline.summarize._call_gemini")
    def test_reaction_failure_preserves_existing_reactions(
        self, mock_gemini: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        mock_gemini.return_value = None
        signals_path = tmp_path / "signals.json"
        signals_path.write_text(json.dumps(SAMPLE_SIGNALS))

        existing_path = tmp_path / "existing.json"
        existing_path.write_text(json.dumps({
            "aspirin": {
                "overall": "Existing overall.",
                "reactions": {"erosive oesophagitis": "Already done."},
            }
        }))

        result = generate_summaries(signals_path, existing_path=existing_path)

        assert result["aspirin"]["overall"] == "Existing overall."
        assert result["aspirin"]["reactions"]["erosive oesophagitis"] == "Already done."
        assert "gi bleeding" not in result["aspirin"]["reactions"]
