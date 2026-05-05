"""Unit tests for ROR/PRR disproportionality analysis.

All tests use manually constructed 2×2 tables with known values so that
the assertions verify the formulas, not just internal consistency.

Reference table (a=10, b=90, c=5, d=895):
  ROR      = (10/90) / (5/895)  = 8950/450  ≈ 19.889
  SE       = √(1/10+1/90+1/5+1/895)          ≈ 0.55878
  ror_lower = exp(ln(ROR) − 1.96·SE)          ≈ 6.636
  ror_upper = exp(ln(ROR) + 1.96·SE)          ≈ 59.46
  PRR      = (10/100) / (5/900)               = 18.0
  N=1000, χ² = 1000·8500² / (100·900·15·985) ≈ 54.33
"""

import math

import pytest
import pandas as pd

from sqlalchemy import create_engine

from analysis.disproportionality import (
    compute_all_signals,
    compute_ror,
    compute_prr,
    flag_signal,
    _contingency_table,
    _ror_from_counts,
    _prr_from_counts,
)

# ── Shared test fixture ──────────────────────────────────────────────────────

A, B, C, D = 10, 90, 5, 895   # reference counts


def _make_df(a: int, b: int, c: int, d: int) -> pd.DataFrame:
    """Build a minimal adverse_events DataFrame from a 2×2 table."""
    rows = (
        [{"drug_name": "drug_x", "reaction": "reaction_y"}] * a
        + [{"drug_name": "drug_x", "reaction": "other_rxn"}] * b
        + [{"drug_name": "other_drug", "reaction": "reaction_y"}] * c
        + [{"drug_name": "other_drug", "reaction": "other_rxn"}] * d
    )
    return pd.DataFrame(rows)


# ── _contingency_table ───────────────────────────────────────────────────────

class TestContingencyTable:
    def test_known_values(self):
        df = _make_df(A, B, C, D)
        a, b, c, d = _contingency_table(df, "drug_x", "reaction_y")
        assert (a, b, c, d) == (A, B, C, D)

    def test_totals_sum_to_n(self):
        df = _make_df(A, B, C, D)
        a, b, c, d = _contingency_table(df, "drug_x", "reaction_y")
        assert a + b + c + d == len(df)

    def test_zero_c_cell(self):
        df = _make_df(5, 10, 0, 85)
        _, _, c, _ = _contingency_table(df, "drug_x", "reaction_y")
        assert c == 0


# ── _ror_from_counts ─────────────────────────────────────────────────────────

class TestRORFromCounts:
    def test_ror_value(self):
        result = _ror_from_counts(A, B, C, D)
        expected = (A / B) / (C / D)
        assert result is not None
        assert math.isclose(result["ror"], expected, rel_tol=1e-9)

    def test_ci_lower(self):
        result = _ror_from_counts(A, B, C, D)
        ror = (A / B) / (C / D)
        se = math.sqrt(1 / A + 1 / B + 1 / C + 1 / D)
        expected = math.exp(math.log(ror) - 1.96 * se)
        assert math.isclose(result["ror_lower"], expected, rel_tol=1e-9)

    def test_ci_upper(self):
        result = _ror_from_counts(A, B, C, D)
        ror = (A / B) / (C / D)
        se = math.sqrt(1 / A + 1 / B + 1 / C + 1 / D)
        expected = math.exp(math.log(ror) + 1.96 * se)
        assert math.isclose(result["ror_upper"], expected, rel_tol=1e-9)

    def test_ci_lower_less_than_ror_less_than_upper(self):
        result = _ror_from_counts(A, B, C, D)
        assert result["ror_lower"] < result["ror"] < result["ror_upper"]

    def test_n_reports_equals_a(self):
        result = _ror_from_counts(A, B, C, D)
        assert result["n_reports"] == A

    def test_zero_a_returns_none_strict(self):
        assert _ror_from_counts(0, B, C, D, continuity_correction=False) is None

    def test_zero_b_returns_none_strict(self):
        assert _ror_from_counts(A, 0, C, D, continuity_correction=False) is None

    def test_zero_c_returns_none_strict(self):
        assert _ror_from_counts(A, B, 0, D, continuity_correction=False) is None

    def test_zero_d_returns_none_strict(self):
        assert _ror_from_counts(A, B, C, 0, continuity_correction=False) is None

    def test_zero_a_with_correction_returns_finite(self):
        result = _ror_from_counts(0, B, C, D)  # default: correction on
        assert result is not None
        assert math.isfinite(result["ror"])
        assert result["n_reports"] == 0  # observed a, not corrected

    def test_zero_b_with_correction_returns_finite(self):
        result = _ror_from_counts(A, 0, C, D)
        assert result is not None
        assert math.isfinite(result["ror"])

    def test_zero_c_with_correction_returns_finite(self):
        result = _ror_from_counts(A, B, 0, D)
        assert result is not None
        assert math.isfinite(result["ror"])

    def test_zero_d_with_correction_returns_finite(self):
        result = _ror_from_counts(A, B, C, 0)
        assert result is not None
        assert math.isfinite(result["ror"])

    def test_drug_absent_returns_none_even_with_correction(self):
        """a + b == 0 → drug entirely absent. Yates does not rescue this."""
        assert _ror_from_counts(0, 0, C, D) is None

    def test_no_comparator_returns_none_even_with_correction(self):
        """c + d == 0 → no comparator drugs. Yates does not rescue this."""
        assert _ror_from_counts(A, B, 0, 0) is None

    def test_via_public_api(self):
        df = _make_df(A, B, C, D)
        result = compute_ror(df, "drug_x", "reaction_y")
        assert result is not None
        assert math.isclose(result["ror"], (A / B) / (C / D), rel_tol=1e-9)

    def test_via_public_api_unknown_drug_returns_none(self):
        """Unknown drug → a + b == 0 → returns None regardless of correction."""
        df = _make_df(A, B, C, D)
        assert compute_ror(df, "unknown_drug", "reaction_y") is None


# ── _prr_from_counts ─────────────────────────────────────────────────────────

class TestPRRFromCounts:
    def test_prr_value(self):
        result = _prr_from_counts(A, B, C, D)
        expected = (A / (A + B)) / (C / (C + D))
        assert result is not None
        assert math.isclose(result["prr"], expected, rel_tol=1e-9)

    def test_chi_squared_exact_pearson(self):
        """Verify chi-squared against the Pearson formula exactly."""
        result = _prr_from_counts(A, B, C, D)
        n = A + B + C + D
        expected = (n * (A * D - B * C) ** 2) / (
            (A + B) * (C + D) * (A + C) * (B + D)
        )
        assert math.isclose(result["chi_squared"], expected, rel_tol=1e-9)

    def test_chi_squared_approximate_value(self):
        """Spot-check: reference table gives χ² ≈ 54.33."""
        result = _prr_from_counts(A, B, C, D)
        assert math.isclose(result["chi_squared"], 54.33, rel_tol=0.01)

    def test_prr_approximate_value(self):
        """Spot-check: reference table gives PRR = 18.0 exactly."""
        result = _prr_from_counts(A, B, C, D)
        assert math.isclose(result["prr"], 18.0, rel_tol=1e-9)

    def test_n_reports_equals_a(self):
        result = _prr_from_counts(A, B, C, D)
        assert result["n_reports"] == A

    def test_zero_a_returns_none_strict(self):
        assert _prr_from_counts(0, B, C, D, continuity_correction=False) is None

    def test_zero_b_returns_none_strict(self):
        assert _prr_from_counts(A, 0, C, D, continuity_correction=False) is None

    def test_zero_c_returns_none_strict(self):
        assert _prr_from_counts(A, B, 0, D, continuity_correction=False) is None

    def test_zero_d_returns_none_strict(self):
        assert _prr_from_counts(A, B, C, 0, continuity_correction=False) is None

    def test_zero_a_with_correction_returns_finite(self):
        result = _prr_from_counts(0, B, C, D)  # default: correction on
        assert result is not None
        assert math.isfinite(result["prr"])
        assert math.isfinite(result["chi_squared"])

    def test_zero_c_with_correction_returns_finite(self):
        result = _prr_from_counts(A, B, 0, D)
        assert result is not None
        assert math.isfinite(result["prr"])

    def test_drug_absent_returns_none_even_with_correction(self):
        assert _prr_from_counts(0, 0, C, D) is None

    def test_no_comparator_returns_none_even_with_correction(self):
        assert _prr_from_counts(A, B, 0, 0) is None

    def test_via_public_api(self):
        df = _make_df(A, B, C, D)
        result = compute_prr(df, "drug_x", "reaction_y")
        assert result is not None
        assert math.isclose(result["prr"], 18.0, rel_tol=1e-9)


# ── flag_signal ───────────────────────────────────────────────────────────────

class TestFlagSignal:
    """All threshold criteria from CLAUDE.md §8.

    ROR lower CI > 1  (strict)
    PRR >= 2          (inclusive)
    n_reports >= 3    (inclusive)
    chi_squared >= 4  (inclusive)
    """

    _ror_pass = {"ror": 5.0, "ror_lower": 2.0, "ror_upper": 12.0, "n_reports": 10}
    _prr_pass = {"prr": 4.0, "chi_squared": 10.0, "n_reports": 10}

    def test_all_thresholds_met(self):
        assert flag_signal(self._ror_pass, self._prr_pass) is True

    def test_none_ror_returns_false(self):
        assert flag_signal(None, self._prr_pass) is False

    def test_none_prr_returns_false(self):
        assert flag_signal(self._ror_pass, None) is False

    def test_both_none_returns_false(self):
        assert flag_signal(None, None) is False

    # ── ROR lower CI threshold (strict > 1) ──────────────────────────────────

    def test_ror_lower_exactly_1_fails(self):
        ror = {**self._ror_pass, "ror_lower": 1.0}
        assert flag_signal(ror, self._prr_pass) is False

    def test_ror_lower_just_above_1_passes(self):
        ror = {**self._ror_pass, "ror_lower": 1.0001}
        assert flag_signal(ror, self._prr_pass) is True

    def test_ror_lower_below_1_fails(self):
        ror = {**self._ror_pass, "ror_lower": 0.99}
        assert flag_signal(ror, self._prr_pass) is False

    # ── PRR threshold (>= 2, inclusive) ──────────────────────────────────────

    def test_prr_exactly_2_passes(self):
        prr = {**self._prr_pass, "prr": 2.0}
        assert flag_signal(self._ror_pass, prr) is True

    def test_prr_just_below_2_fails(self):
        prr = {**self._prr_pass, "prr": 1.999}
        assert flag_signal(self._ror_pass, prr) is False

    def test_prr_above_2_passes(self):
        prr = {**self._prr_pass, "prr": 2.001}
        assert flag_signal(self._ror_pass, prr) is True

    # ── n_reports threshold (>= 3, inclusive) ────────────────────────────────

    def test_n_exactly_3_passes(self):
        prr = {**self._prr_pass, "n_reports": 3}
        assert flag_signal(self._ror_pass, prr) is True

    def test_n_2_fails(self):
        prr = {**self._prr_pass, "n_reports": 2}
        assert flag_signal(self._ror_pass, prr) is False

    def test_n_1_fails(self):
        prr = {**self._prr_pass, "n_reports": 1}
        assert flag_signal(self._ror_pass, prr) is False

    # ── chi-squared threshold (>= 4, inclusive) ───────────────────────────────

    def test_chi2_exactly_4_passes(self):
        prr = {**self._prr_pass, "chi_squared": 4.0}
        assert flag_signal(self._ror_pass, prr) is True

    def test_chi2_just_below_4_fails(self):
        prr = {**self._prr_pass, "chi_squared": 3.999}
        assert flag_signal(self._ror_pass, prr) is False

    def test_chi2_above_4_passes(self):
        prr = {**self._prr_pass, "chi_squared": 4.001}
        assert flag_signal(self._ror_pass, prr) is True

    # ── All four criteria must pass simultaneously ────────────────────────────

    def test_only_ror_fails_is_not_signal(self):
        ror = {**self._ror_pass, "ror_lower": 0.5}
        assert flag_signal(ror, self._prr_pass) is False

    def test_only_prr_fails_is_not_signal(self):
        prr = {**self._prr_pass, "prr": 1.0}
        assert flag_signal(self._ror_pass, prr) is False


# ── compute_all_signals ──────────────────────────────────────────────────────

class TestComputeAllSignals:
    """End-to-end behaviour of the batch signal computation against an
    in-memory SQLite database. Verifies the EVANS-criterion ``min_reports``
    floor and continuity-correction flag are honoured."""

    @staticmethod
    def _engine_with(df: pd.DataFrame):
        """Spin up an in-memory SQLite engine pre-populated with rows."""
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            df.to_sql("adverse_events", conn, if_exists="replace", index=False)
            conn.commit()
        return engine

    def test_empty_table_returns_empty_frame(self):
        engine = self._engine_with(pd.DataFrame(columns=["drug_name", "reaction"]))
        result = compute_all_signals(engine)
        assert result.empty
        assert "chi_squared" in result.columns

    def test_min_reports_filters_low_count_pair(self):
        # Two drugs, two reactions. drug_x/rxn_a has a=2; drug_x/rxn_b has a=4.
        # With min_reports=3 (default), only the a=4 pair survives.
        rows = (
            [{"drug_name": "drug_x", "reaction": "rxn_a"}] * 2
            + [{"drug_name": "drug_x", "reaction": "rxn_b"}] * 4
            + [{"drug_name": "other", "reaction": "rxn_a"}] * 50
            + [{"drug_name": "other", "reaction": "rxn_b"}] * 50
        )
        engine = self._engine_with(pd.DataFrame(rows))

        result = compute_all_signals(engine)  # default min_reports=3
        pairs = set(zip(result["drug_name"], result["reaction"]))
        assert ("drug_x", "rxn_b") in pairs
        assert ("drug_x", "rxn_a") not in pairs

    def test_min_reports_one_includes_low_count_pair(self):
        rows = (
            [{"drug_name": "drug_x", "reaction": "rxn_a"}] * 2
            + [{"drug_name": "drug_x", "reaction": "rxn_b"}] * 4
            + [{"drug_name": "other", "reaction": "rxn_a"}] * 50
            + [{"drug_name": "other", "reaction": "rxn_b"}] * 50
        )
        engine = self._engine_with(pd.DataFrame(rows))

        result = compute_all_signals(engine, min_reports=1)
        pairs = set(zip(result["drug_name"], result["reaction"]))
        assert ("drug_x", "rxn_a") in pairs
        assert ("drug_x", "rxn_b") in pairs

    def test_chi_squared_in_output(self):
        rows = (
            [{"drug_name": "drug_x", "reaction": "rxn_a"}] * 10
            + [{"drug_name": "other", "reaction": "rxn_a"}] * 5
            + [{"drug_name": "other", "reaction": "rxn_b"}] * 95
        )
        engine = self._engine_with(pd.DataFrame(rows))

        result = compute_all_signals(engine)
        assert "chi_squared" in result.columns
        # No zero cells here, so every chi_squared should be finite and positive.
        assert (result["chi_squared"] > 0).all()
