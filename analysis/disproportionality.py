"""Disproportionality analysis — ROR and PRR signal detection.

Implements the 2×2 contingency table approach from Rothman et al. (2004),
following the formulas in CLAUDE.md §8 exactly.

2×2 notation:
  a = reports of drug X WITH reaction Y
  b = reports of drug X WITHOUT reaction Y
  c = reports of all other drugs WITH reaction Y
  d = reports of all other drugs WITHOUT reaction Y

ROR  = (a/b) / (c/d)
  95% CI: SE = sqrt(1/a + 1/b + 1/c + 1/d)
          lower = exp(ln(ROR) − 1.96·SE),  upper = exp(ln(ROR) + 1.96·SE)
  Signal threshold: lower > 1 (strict)

PRR  = (a / (a+b)) / (c / (c+d))
  χ² = N·(ad − bc)² / [(a+b)(c+d)(a+c)(b+d)]   — exact Pearson, no Yates
  Signal thresholds: PRR ≥ 2 AND n ≥ 3 AND χ² ≥ 4

All four public functions return None (rather than raising) when a cell is
zero so callers can handle missing-data cases uniformly.
"""

import logging
import math
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────────────────

def compute_ror(df: pd.DataFrame, drug_name: str, reaction: str) -> dict | None:
    """Compute ROR and 95% CI for one drug-reaction pair.

    Args:
        df:        DataFrame with columns drug_name, reaction (at minimum).
        drug_name: Drug of interest.
        reaction:  Reaction of interest.

    Returns:
        dict with keys ror, ror_lower, ror_upper, n_reports
        or None if any contingency cell is zero (log-SE undefined).
    """
    a, b, c, d = _contingency_table(df, drug_name, reaction)
    return _ror_from_counts(a, b, c, d)


def compute_prr(df: pd.DataFrame, drug_name: str, reaction: str) -> dict | None:
    """Compute PRR and chi-squared for one drug-reaction pair.

    Args:
        df:        DataFrame with columns drug_name, reaction (at minimum).
        drug_name: Drug of interest.
        reaction:  Reaction of interest.

    Returns:
        dict with keys prr, chi_squared, n_reports
        or None if any contingency cell is zero.
    """
    a, b, c, d = _contingency_table(df, drug_name, reaction)
    return _prr_from_counts(a, b, c, d)


def flag_signal(ror_result: dict | None, prr_result: dict | None) -> bool:
    """Return True if both ROR and PRR thresholds are met (CLAUDE.md §8).

    Criteria:
      ROR lower 95% CI > 1   (strict inequality)
      PRR >= 2
      n_reports >= 3
      chi_squared >= 4
    """
    if ror_result is None or prr_result is None:
        return False
    return (
        ror_result["ror_lower"] > 1.0
        and prr_result["prr"] >= 2.0
        and prr_result["n_reports"] >= 3
        and prr_result["chi_squared"] >= 4.0
    )


def compute_all_signals(engine: Engine) -> pd.DataFrame:
    """Compute ROR/PRR for every drug-reaction pair in adverse_events.

    Uses vectorised groupby counts rather than per-row DataFrame scans —
    precomputes pair, drug, and reaction totals once then resolves each
    2×2 table in O(1).

    Returns:
        DataFrame with columns matching signal_scores schema (no id column):
        drug_name, reaction, ror, ror_lower, ror_upper, prr, n_reports, computed_date
        Pairs where any contingency cell is zero are dropped.
    """
    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT drug_name, reaction FROM adverse_events"), conn
        )

    if df.empty:
        logger.warning("adverse_events is empty — no signals to compute")
        return pd.DataFrame(
            columns=["drug_name", "reaction", "ror", "ror_lower", "ror_upper",
                     "prr", "n_reports", "computed_date"]
        )

    n_total = len(df)
    pair_counts = df.groupby(["drug_name", "reaction"]).size()
    drug_counts = df.groupby("drug_name").size()
    reaction_counts = df.groupby("reaction").size()

    rows = []
    skipped = 0
    today = date.today()

    for (drug, rxn), a in pair_counts.items():
        b = int(drug_counts[drug]) - a
        c = int(reaction_counts[rxn]) - a
        d = n_total - a - b - c

        ror = _ror_from_counts(a, b, c, d)
        prr = _prr_from_counts(a, b, c, d)

        if ror is None or prr is None:
            skipped += 1
            continue

        rows.append({
            "drug_name": drug,
            "reaction": rxn,
            "ror": ror["ror"],
            "ror_lower": ror["ror_lower"],
            "ror_upper": ror["ror_upper"],
            "prr": prr["prr"],
            "n_reports": a,
            "computed_date": today,
        })

    logger.info(
        "Computed signals for %d pairs; %d skipped (zero-cell)", len(rows), skipped
    )
    return pd.DataFrame(rows)


# ── Private helpers ──────────────────────────────────────────────────────────

def _contingency_table(
    df: pd.DataFrame, drug_name: str, reaction: str
) -> tuple[int, int, int, int]:
    """Extract (a, b, c, d) counts from an adverse_events DataFrame."""
    is_drug = df["drug_name"] == drug_name
    is_rxn = df["reaction"] == reaction

    a = int((is_drug & is_rxn).sum())
    b = int((is_drug & ~is_rxn).sum())
    c = int((~is_drug & is_rxn).sum())
    d = int((~is_drug & ~is_rxn).sum())

    return a, b, c, d


def _ror_from_counts(a: int, b: int, c: int, d: int) -> dict | None:
    """Compute ROR and 95% CI from raw (a, b, c, d).

    Returns None when any cell is zero — log-normal SE is undefined.
    """
    if a == 0 or b == 0 or c == 0 or d == 0:
        return None

    ror = (a / b) / (c / d)
    log_ror = math.log(ror)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)

    return {
        "ror": ror,
        "ror_lower": math.exp(log_ror - 1.96 * se),
        "ror_upper": math.exp(log_ror + 1.96 * se),
        "n_reports": a,
    }


def _prr_from_counts(a: int, b: int, c: int, d: int) -> dict | None:
    """Compute PRR and Pearson chi-squared from raw (a, b, c, d).

    Chi-squared uses the exact Pearson formula — no Yates' continuity correction.
    Returns None when any cell is zero.
    """
    if a == 0 or b == 0 or c == 0 or d == 0:
        return None

    prr = (a / (a + b)) / (c / (c + d))

    n = a + b + c + d
    chi_squared = (n * (a * d - b * c) ** 2) / (
        (a + b) * (c + d) * (a + c) * (b + d)
    )

    return {
        "prr": prr,
        "chi_squared": chi_squared,
        "n_reports": a,
    }
