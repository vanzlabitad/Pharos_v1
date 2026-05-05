"""OpenFDA FAERS adverse event ingestion.

Fetches reports for a given drug name and returns a raw DataFrame
with one row per (report, reaction) pair. Normalisation is handled
downstream in clean.py.

Columns returned:
  safetyreportid, drug_name, reaction, outcome, report_date, serious, source
"""

import logging
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from pipeline.normalise import canonical

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.fda.gov/drug/event.json"
_PAGE_SIZE = 1000   # OpenFDA maximum per request
_REQUEST_TIMEOUT = 10   # seconds

# Retry policy on HTTP 429 (rate limit). Three attempts with exponential
# backoff (1s, 2s, 4s) before raising. Failure is loud — no partial-data
# fallback — so the cron exits non-zero and GitHub Actions emails the user.
_RATE_LIMIT_RETRY_DELAYS = (1, 2, 4)


class RateLimitExceededError(RuntimeError):
    """Raised when OpenFDA returns 429 after all retries are exhausted."""


def fetch_adverse_events(drug_name: str, max_records: int = 5000) -> pd.DataFrame:
    """Fetch adverse event reports for drug_name from OpenFDA FAERS.

    Paginates until max_records reached or the API is exhausted.
    Returns a raw DataFrame; never raises — logs failures and returns
    whatever was collected (may be empty on complete failure).

    Args:
        drug_name:   Drug name as it appears in OpenFDA (case-insensitive).
        max_records: Upper bound on total rows to fetch. Defaults to 5000.

    Returns:
        DataFrame with columns:
          safetyreportid, drug_name, reaction, outcome,
          report_date, serious, source
    """
    api_key = os.getenv("OPENFDA_API_KEY", "")
    rows: list[dict] = []
    skip = 0

    while len(rows) < max_records:
        limit = min(_PAGE_SIZE, max_records - len(rows))
        page_rows = _fetch_page(drug_name, skip, limit, api_key)

        if page_rows is None:
            # Unrecoverable error for this page — stop paginating
            break

        rows.extend(page_rows)

        if len(page_rows) < limit:
            # API returned fewer records than requested — we've hit the end
            break

        skip += limit
        # Be polite to the API between pages
        time.sleep(0.2)

    if not rows:
        logger.warning("No rows collected for drug '%s'", drug_name)
        return _empty_frame()

    df = pd.DataFrame(rows)
    logger.info("Fetched %d raw rows for '%s'", len(df), drug_name)
    return df


def _fetch_page(
    drug_name: str, skip: int, limit: int, api_key: str
) -> list[dict] | None:
    """Fetch one page of results. Returns list of row dicts, or None on failure.

    On HTTP 429, retries with exponential backoff (1s → 2s → 4s) before
    raising ``RateLimitExceededError``. Other failures (timeout, network,
    non-2xx, malformed JSON) return None and stop pagination for this drug.
    """
    params: dict = {
        "search": f'patient.drug.medicinalproduct:"{drug_name}"',
        "limit": limit,
        "skip": skip,
    }
    if api_key:
        params["api_key"] = api_key

    response = None
    for attempt, delay in enumerate((0,) + _RATE_LIMIT_RETRY_DELAYS):
        if delay:
            logger.warning(
                "OpenFDA 429 on '%s' (skip=%d) — retry %d/%d after %ds",
                drug_name, skip, attempt, len(_RATE_LIMIT_RETRY_DELAYS), delay,
            )
            time.sleep(delay)

        try:
            response = requests.get(_BASE_URL, params=params, timeout=_REQUEST_TIMEOUT)
        except requests.Timeout:
            logger.warning(
                "Timeout fetching page skip=%d for '%s' — stopping pagination",
                skip, drug_name,
            )
            return None
        except requests.RequestException as exc:
            logger.warning(
                "Network error fetching page skip=%d for '%s': %s",
                skip, drug_name, exc,
            )
            return None

        if response.status_code != 429:
            break
    else:
        # Loop exhausted without breaking — every attempt was a 429.
        raise RateLimitExceededError(
            f"OpenFDA returned 429 for '{drug_name}' (skip={skip}) after "
            f"{len(_RATE_LIMIT_RETRY_DELAYS)} retries"
        )

    assert response is not None  # for type-checker; loop guarantees this

    if response.status_code == 404:
        logger.warning("OpenFDA returned 404 for drug '%s' — no results found", drug_name)
        return []   # Empty list, not None: this is expected, not an error

    if not response.ok:
        logger.warning(
            "OpenFDA returned HTTP %d for '%s' (skip=%d)",
            response.status_code, drug_name, skip,
        )
        return None

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Failed to parse JSON for '%s' skip=%d: %s", drug_name, skip, exc)
        return None

    results = data.get("results", [])
    if not results:
        return []

    return _parse_results(results, drug_name)


def _parse_results(results: list[dict], drug_name: str) -> list[dict]:
    """Explode each report into one row per reaction."""
    rows = []
    for report in results:
        report_id = report.get("safetyreportid", "")
        receive_date = report.get("receivedate", "")
        serious = _coerce_serious(report.get("serious"))

        patient = report.get("patient", {})
        reactions = patient.get("reaction", [])

        if not reactions:
            continue

        canonical_name = canonical(drug_name)
        for rxn in reactions:
            rows.append({
                "safetyreportid": report_id,
                "drug_name": canonical_name,
                "reaction": rxn.get("reactionmeddrapt", ""),
                "outcome": str(rxn.get("reactionoutcome", "")),
                "report_date": receive_date,
                "serious": serious,
                "source": "openfda_faers",
            })

    return rows


def _coerce_serious(value) -> int:
    """Map OpenFDA 'serious' field to 1/0. Field is 1=serious, 2=not serious."""
    try:
        return 1 if int(value) == 1 else 0
    except (TypeError, ValueError):
        return 0


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["safetyreportid", "drug_name", "reaction", "outcome",
                 "report_date", "serious", "source"]
    )
