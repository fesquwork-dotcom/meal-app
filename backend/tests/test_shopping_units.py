from decimal import Decimal

import pytest

from shopping.units import (
    DEFAULT_UNIT_POLICY,
    CanonicalUnitPolicy,
    format_decimal_plain,
    format_weight,
    merge_quantities,
    parse_amount,
)


def test_parse_decimal_and_comma():
    parsed = parse_amount("2,5 кг")
    assert parsed.quantity == Decimal("2.5")
    assert parsed.unit == "kg"


def test_parse_fraction():
    parsed = parse_amount("1/2 кг")
    assert parsed.quantity == Decimal("0.5")
    assert parsed.unit == "kg"


def test_non_numeric_to_taste():
    parsed = parse_amount("по вкусу")
    assert parsed.unit == "to_taste"
    assert parsed.aggregatable is False


def test_merge_kg_and_g():
    merged = merge_quantities(Decimal("1"), "kg", Decimal("500"), "g")
    assert merged == (Decimal("1500"), "g")


def test_merge_l_and_ml():
    merged = merge_quantities(Decimal("1"), "l", Decimal("250"), "ml")
    assert merged == (Decimal("1250"), "ml")


def test_incompatible_units_do_not_merge():
    assert merge_quantities(Decimal("100"), "g", Decimal("100"), "ml") is None
    assert merge_quantities(Decimal("1"), "package", Decimal("100"), "g") is None


# --- Sprint 10.5.1: no scientific notation in weights (contract) -------------------


@pytest.mark.parametrize(
    ("quantity", "expected"),
    [
        (Decimal("100"), "100 г"),
        (Decimal("500"), "500 г"),
        (Decimal("1200"), "1200 г"),
        (Decimal("1250.5"), "1250.5 г"),
        (Decimal("1.2500"), "1.25 г"),
    ],
)
def test_format_weight_never_uses_scientific_notation(quantity, expected):
    result = format_weight(quantity, "g", raw_fallback="")
    assert result == expected
    assert "E" not in result and "e" not in result


def test_merged_round_totals_format_plain():
    merged = merge_quantities(Decimal("400"), "g", Decimal("800"), "g")
    assert merged == (Decimal("1200"), "g")
    assert format_weight(merged[0], merged[1], raw_fallback="") == "1200 г"


@pytest.mark.parametrize(
    ("quantity", "expected"),
    [
        (Decimal("1E+2"), "100"),
        (Decimal("1.2E+3"), "1200"),
        (Decimal("2E5"), "200000"),
        (Decimal("8E+2"), "800"),
        (Decimal("0.5000"), "0.5"),
    ],
)
def test_format_decimal_plain_expands_exponent_forms(quantity, expected):
    assert format_decimal_plain(quantity) == expected


def test_default_unit_policy_is_noop():
    policy = CanonicalUnitPolicy()
    assert policy.resolve_unit("помидор", "pcs") == "pcs"
    assert policy.resolve_unit("помидор", "g") == "g"
    assert DEFAULT_UNIT_POLICY.resolve_unit("рис", "kg") == "kg"
