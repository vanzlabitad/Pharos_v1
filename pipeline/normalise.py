"""Drug-name canonicalisation.

Maps common brand names and variant spellings to a canonical generic name
so that disproportionality analysis aggregates reports correctly. Without
this step, "ADVIL" and "ibuprofen" would be treated as two separate drugs
and signals would be diluted across both.

Strategy:
  1. Lower-case + trim the input.
  2. Look up in alias table (loaded from pipeline/drug_aliases.json).
  3. Fall through to the lower/trimmed input if unmapped.

Coverage is curated and intentionally narrow — RxNorm integration is a V2
goal (see CLAUDE.md §8 limitations).
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_ALIAS_FILE = Path(__file__).parent / "drug_aliases.json"


@lru_cache(maxsize=1)
def _load_aliases() -> dict[str, str]:
    """Load and normalise the alias table once per process."""
    if not _ALIAS_FILE.exists():
        logger.warning(
            "Alias file %s missing; canonical() falls through to lower+strip only",
            _ALIAS_FILE,
        )
        return {}
    with _ALIAS_FILE.open(encoding="utf-8") as f:
        raw: dict[str, str] = json.load(f)
    return {k.lower().strip(): v.lower().strip() for k, v in raw.items()}


def canonical(drug_name: str | None) -> str:
    """Return the canonical lower-case name for a drug.

    Args:
        drug_name: Raw drug name as reported (or None / empty string).

    Returns:
        Canonical name. Empty input returns "". Unmapped names fall through
        to ``drug_name.lower().strip()`` with no further transformation.
    """
    if not drug_name:
        return ""
    key = drug_name.lower().strip()
    return _load_aliases().get(key, key)


def reset_alias_cache() -> None:
    """Clear the alias-table cache. Used by tests after monkey-patching the file."""
    _load_aliases.cache_clear()
