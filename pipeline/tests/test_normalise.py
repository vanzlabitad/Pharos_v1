"""Unit tests for pipeline.normalise.canonical drug-name canonicalisation."""

import pytest

from pipeline.normalise import canonical, reset_alias_cache


@pytest.fixture(autouse=True)
def _reset_cache():
    """Make sure the LRU cache does not leak alias state between tests."""
    reset_alias_cache()
    yield
    reset_alias_cache()


class TestCanonical:
    def test_known_brand_maps_to_generic(self):
        assert canonical("ADVIL") == "ibuprofen"

    def test_lowercase_brand_maps_to_generic(self):
        assert canonical("advil") == "ibuprofen"

    def test_mixed_case_maps_to_generic(self):
        assert canonical("Advil") == "ibuprofen"

    def test_brand_with_whitespace_maps_to_generic(self):
        assert canonical("  ADVIL  ") == "ibuprofen"

    def test_unknown_drug_falls_through_to_lower_strip(self):
        assert canonical("UNKNOWN_DRUG") == "unknown_drug"

    def test_unknown_drug_with_whitespace_falls_through(self):
        assert canonical("  Some Drug ") == "some drug"

    def test_empty_string_returns_empty(self):
        assert canonical("") == ""

    def test_none_returns_empty(self):
        assert canonical(None) == ""

    def test_already_canonical_passes_through(self):
        # Generic names that are *values* in the alias table should pass
        # through unchanged (they are not keys, so fall through to lower+strip).
        assert canonical("ibuprofen") == "ibuprofen"

    def test_multiple_brands_map_to_same_generic(self):
        assert canonical("advil") == canonical("motrin") == canonical("nurofen")
