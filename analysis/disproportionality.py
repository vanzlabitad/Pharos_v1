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

Zero-cell handling (Rothman 2004, §15):
  When any cell is zero, the log-SE is undefined and PRR is unstable. By
  default this module applies Yates' 0.5 continuity correction — adds 0.5
  to every cell — and returns finite estimates. Callers that need strict
  behaviour (skip the pair entirely) pass ``continuity_correction=False``,
  in which case the function returns None.

  ``n_reports`` always reflects the *observed* a, not the corrected value.
  This means a corrected pair with observed a < 3 will still fail the
  EVANS-criterion floor in ``flag_signal``, so Yates does not promote noise
  into signals.

Cell-inclusion floor (Evans 2001):
  ``compute_all_signals`` skips pairs with observed a < ``min_reports``
  (default 3). This is the EVANS-criterion floor for PRR signal detection
  and matches standard ROR practice.
"""

import logging
import math
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────────────────

def compute_ror(
    df: pd.DataFrame,
    drug_name: str,
    reaction: str,
    *,
    continuity_correction: bool = True,
) -> dict | None:
    """Compute ROR and 95% CI for one drug-reaction pair.

    Args:
        df:        DataFrame with columns drug_name, reaction (at minimum).
        drug_name: Drug of interest.
        reaction:  Reaction of interest.
        continuity_correction: If True (default), apply Yates' 0.5 correction
            when any cell is zero. If False, return None on any zero cell.

    Returns:
        dict with keys ror, ror_lower, ror_upper, n_reports
        or None if a zero cell is encountered with correction disabled.
    """
    a, b, c, d = _contingency_table(df, drug_name, reaction)
    return _ror_from_counts(a, b, c, d, continuity_correction=continuity_correction)


def compute_prr(
    df: pd.DataFrame,
    drug_name: str,
    reaction: str,
    *,
    continuity_correction: bool = True,
) -> dict | None:
    """Compute PRR and chi-squared for one drug-reaction pair.

    Args:
        df:        DataFrame with columns drug_name, reaction (at minimum).
        drug_name: Drug of interest.
        reaction:  Reaction of interest.
        continuity_correction: If True (default), apply Yates' 0.5 correction
            when any cell is zero. If False, return None on any zero cell.

    Returns:
        dict with keys prr, chi_squared, n_reports
        or None if a zero cell is encountered with correction disabled.
    """
    a, b, c, d = _contingency_table(df, drug_name, reaction)
    return _prr_from_counts(a, b, c, d, continuity_correction=continuity_correction)


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


def compute_all_signals(
    engine: Engine,
    *,
    continuity_correction: bool = True,
    min_reports: int = 3,
) -> pd.DataFrame:
    """Compute ROR/PRR for every drug-reaction pair in adverse_events.

    Uses vectorised groupby counts rather than per-row DataFrame scans —
    precomputes pair, drug, and reaction totals once then resolves each
    2×2 table in O(1).

    Args:
        engine: SQLAlchemy engine bound to the Pharos database.
        continuity_correction: If True (default), apply Yates' 0.5 correction
            on zero-cell pairs rather than dropping them.
        min_reports: Minimum observed ``a`` (drug-reaction co-occurrence) for
            a pair to be computed at all. Defaults to 3, the EVANS-criterion
            floor (Evans 2001) for stable PRR estimation. Pairs below this
            floor are skipped, not corrected.

    Returns:
        DataFrame with columns matching signal_scores schema:
        drug_name, reaction, ror, ror_lower, ror_upper, prr,
        chi_squared, n_reports, computed_date.
    """
    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT drug_name, reaction FROM adverse_events"), conn
        )

    cols = ["drug_name", "reaction", "ror", "ror_lower", "ror_upper",
            "prr", "chi_squared", "n_reports", "computed_date"]

    if df.empty:
        logger.warning("adverse_events is empty — no signals to compute")
        return pd.DataFrame(columns=cols)

    n_total = len(df)
    pair_counts = df.groupby(["drug_name", "reaction"]).size()
    drug_counts = df.groupby("drug_name").size()
    reaction_counts = df.groupby("reaction").size()

    rows = []
    skipped_low_count = 0
    skipped_zero_cell = 0
    today = date.today()

    for (drug, rxn), a in pair_counts.items():
        if a < min_reports:
            skipped_low_count += 1
            continue

        b = int(drug_counts[drug]) - a
        c = int(reaction_counts[rxn]) - a
        d = n_total - a - b - c

        ror = _ror_from_counts(a, b, c, d, continuity_correction=continuity_correction)
        prr = _prr_from_counts(a, b, c, d, continuity_correction=continuity_correction)

        if ror is None or prr is None:
            skipped_zero_cell += 1
            continue

        rows.append({
            "drug_name": drug,
            "reaction": rxn,
            "ror": ror["ror"],
            "ror_lower": ror["ror_lower"],
            "ror_upper": ror["ror_upper"],
            "prr": prr["prr"],
            "chi_squared": prr["chi_squared"],
            "n_reports": a,
            "computed_date": today,
        })

    logger.info(
        "Computed signals for %d pairs; %d skipped (a < %d), %d skipped (zero-cell, correction=%s)",
        len(rows), skipped_low_count, min_reports, skipped_zero_cell, continuity_correction,
    )
    return pd.DataFrame(rows, columns=cols)


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


def _ror_from_counts(
    a: int, b: int, c: int, d: int, *, continuity_correction: bool = True
) -> dict | None:
    """Compute ROR and 95% CI from raw (a, b, c, d).

    When any cell is zero, log-normal SE is undefined. With
    ``continuity_correction=True`` (default), 0.5 is added to every cell
    before computing (Yates correction; Rothman 2004 §15). With False,
    return None.

    Yates does not rescue "drug entirely absent" (a + b == 0) or "no
    comparator" (c + d == 0); those return None regardless.

    ``n_reports`` is always the observed ``a``, not the corrected value.
    """
    if a + b == 0 or c + d == 0:
        return None
    if a == 0 or b == 0 or c == 0 or d == 0:
        if not continuity_correction:
            return None
        a_, b_, c_, d_ = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    else:
        a_, b_, c_, d_ = a, b, c, d

    ror = (a_ / b_) / (c_ / d_)
    log_ror = math.log(ror)
    se = math.sqrt(1 / a_ + 1 / b_ + 1 / c_ + 1 / d_)

    return {
        "ror": ror,
        "ror_lower": math.exp(log_ror - 1.96 * se),
        "ror_upper": math.exp(log_ror + 1.96 * se),
        "n_reports": a,
    }


def _prr_from_counts(
    a: int, b: int, c: int, d: int, *, continuity_correction: bool = True
) -> dict | None:
    """Compute PRR and Pearson chi-squared from raw (a, b, c, d).

    Chi-squared uses the exact Pearson formula. When any cell is zero and
    ``continuity_correction`` is True (default), 0.5 is added to every cell
    before computing (Rothman 2004 §15). With False, return None.

    Yates does not rescue "drug entirely absent" (a + b == 0) or "no
    comparator" (c + d == 0); those return None regardless.

    ``n_reports`` is always the observed ``a``, not the corrected value.
    """
    if a + b == 0 or c + d == 0:
        return None
    if a == 0 or b == 0 or c == 0 or d == 0:
        if not continuity_correction:
            return None
        a_, b_, c_, d_ = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    else:
        a_, b_, c_, d_ = a, b, c, d

    prr = (a_ / (a_ + b_)) / (c_ / (c_ + d_))

    n = a_ + b_ + c_ + d_
    chi_squared = (n * (a_ * d_ - b_ * c_) ** 2) / (
        (a_ + b_) * (c_ + d_) * (a_ + c_) * (b_ + d_)
    )

    return {
        "prr": prr,
        "chi_squared": chi_squared,
        "n_reports": a,
    }
