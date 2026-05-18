"""AI plain-language summary generation via Gemini API.

Reads exported signal data, identifies drugs with flagged signals,
and generates 2-3 sentence plain-language summaries using Gemini 2.5 Flash.

Generated at refresh time only -- never from the browser.
Output cached in dashboard/public/data/summaries.json.
"""

import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"
_MAX_DRUGS_PER_REFRESH = 200
_RETRY_DELAY = 2
_RATE_LIMIT_DELAY = 15
_INTER_CALL_DELAY = 13

_PROMPT_TEMPLATE = """\
You are a plain-language medical writer. Given the following drug safety \
signal data, write a 2-3 sentence summary a non-scientist can understand.

Constraints:
- Do not give medical advice, dosage recommendations, or guidance on \
whether to take or avoid the drug.
- Describe the statistical signal only -- what it measures and what it \
does and does not tell us.
- Do not use jargon (or define it briefly when unavoidable).

Drug: {drug_name}
Top reaction: {top_reaction}
ROR: {ror} (95% CI: {ror_lower}-{ror_upper})
n_reports: {n_reports}
Signal flagged: {flagged}

Output only the summary. No preamble."""

_REACTION_PROMPT_TEMPLATE = """\
You are a plain-language medical writer. Explain what "{reaction}" means \
in plain terms, then describe the statistical finding for {drug_name}. \
2-3 sentences a non-scientist can understand.

Constraints:
- Do not give medical advice, dosage recommendations, or guidance on \
whether to take or avoid the drug.
- Describe the statistical signal only -- what it measures and what it \
does and does not tell us.
- Do not use jargon (or define it briefly when unavoidable).

Drug: {drug_name}
Reaction: {reaction}
ROR: {ror} (95% CI: {ror_lower}-{ror_upper})
n_reports: {n_reports}

Output only the explanation. No preamble."""


def _build_prompt(
    drug_name: str,
    top_reaction: str,
    ror: float,
    ror_lower: float,
    ror_upper: float,
    n_reports: int,
    flagged: bool,
) -> str:
    return _PROMPT_TEMPLATE.format(
        drug_name=drug_name,
        top_reaction=top_reaction,
        ror=f"{ror:.2f}",
        ror_lower=f"{ror_lower:.2f}",
        ror_upper=f"{ror_upper:.2f}",
        n_reports=n_reports,
        flagged="Yes" if flagged else "No",
    )


def _build_reaction_prompt(
    drug_name: str,
    reaction: str,
    ror: float,
    ror_lower: float,
    ror_upper: float,
    n_reports: int,
) -> str:
    return _REACTION_PROMPT_TEMPLATE.format(
        drug_name=drug_name,
        reaction=reaction,
        ror=f"{ror:.2f}",
        ror_lower=f"{ror_lower:.2f}",
        ror_upper=f"{ror_upper:.2f}",
        n_reports=n_reports,
    )


def _get_top_flagged_signal(
    signals: list[dict], drug_name: str
) -> dict | None:
    flagged = [
        s for s in signals if s["drug_name"] == drug_name and s.get("flagged")
    ]
    if not flagged:
        return None
    return max(flagged, key=lambda s: s["ror"])


def _get_top_flagged_signals(
    signals: list[dict], drug_name: str, limit: int = 15
) -> list[dict]:
    flagged = [
        s for s in signals if s["drug_name"] == drug_name and s.get("flagged")
    ]
    return sorted(flagged, key=lambda s: s["ror"], reverse=True)[:limit]


def _call_gemini(prompt: str, api_key: str) -> str | None:
    try:
        from google import genai
    except ImportError:
        logger.error("google-genai package not installed -- skipping")
        return None

    client = genai.Client(api_key=api_key)

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=_MODEL, contents=prompt
            )
            return response.text.strip()
        except Exception as exc:
            exc_name = type(exc).__name__
            is_rate_limit = "429" in str(exc) or "ResourceExhausted" in exc_name
            delay = _RATE_LIMIT_DELAY if is_rate_limit else _RETRY_DELAY

            if attempt == 0:
                logger.warning(
                    "Gemini API error (%s), retrying in %ds...", exc_name, delay
                )
                time.sleep(delay)
            else:
                logger.error("Gemini API failed after retry: %s", exc)
                return None

    return None


def generate_summaries(
    signals_path: Path,
) -> dict[str, dict[str, str | dict[str, str]]]:
    """Generate plain-language summaries for drugs with flagged signals.

    Returns nested dict: {drug: {"overall": "...", "reactions": {"name": "..."}}}
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set -- skipping summary generation")
        return {}

    if not signals_path.exists():
        logger.warning("signals.json not found at %s", signals_path)
        return {}

    signals: list[dict] = json.loads(signals_path.read_text(encoding="utf-8"))

    drugs_with_flags = sorted(
        {s["drug_name"] for s in signals if s.get("flagged")}
    )

    if not drugs_with_flags:
        logger.info("No drugs with flagged signals -- nothing to summarise")
        return {}

    drugs_with_flags = drugs_with_flags[:_MAX_DRUGS_PER_REFRESH]
    logger.info("Generating summaries for %d drugs...", len(drugs_with_flags))

    summaries: dict[str, dict[str, str | dict[str, str]]] = {}

    for i, drug in enumerate(drugs_with_flags, 1):
        top = _get_top_flagged_signal(signals, drug)
        if not top:
            continue

        prompt = _build_prompt(
            drug_name=drug,
            top_reaction=top["reaction"],
            ror=top["ror"],
            ror_lower=top["ror_lower"],
            ror_upper=top["ror_upper"],
            n_reports=top["n_reports"],
            flagged=top["flagged"],
        )

        overall_text = _call_gemini(prompt, api_key)
        if not overall_text:
            logger.warning("Skipped summary for %s (API error)", drug)
            continue

        logger.info(
            "Generated overall summary for %s (%d/%d)",
            drug, i, len(drugs_with_flags),
        )
        time.sleep(_INTER_CALL_DELAY)

        reaction_summaries: dict[str, str] = {}
        top_signals = _get_top_flagged_signals(signals, drug, limit=15)

        for sig in top_signals:
            rprompt = _build_reaction_prompt(
                drug_name=drug,
                reaction=sig["reaction"],
                ror=sig["ror"],
                ror_lower=sig["ror_lower"],
                ror_upper=sig["ror_upper"],
                n_reports=sig["n_reports"],
            )
            rtext = _call_gemini(rprompt, api_key)
            if rtext:
                reaction_summaries[sig["reaction"]] = rtext
            time.sleep(_INTER_CALL_DELAY)

        summaries[drug] = {
            "overall": overall_text,
            "reactions": reaction_summaries,
        }
        logger.info(
            "Generated %d reaction summaries for %s",
            len(reaction_summaries), drug,
        )

    return summaries


def export_summaries_json(
    summaries: dict[str, dict[str, str | dict[str, str]]], output_path: Path
) -> int:
    """Write summaries to JSON file. Returns number of summaries written."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(summaries)
