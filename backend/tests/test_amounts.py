"""Tests for amount parsing (signed amounts, quirks, errors)."""

import pytest

from app.parsing.amounts import parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("-54.99", -5499),
        ("54.99", 5499),
        ("0.00", 0),
        ("$1,234.56", 123456),
        ("(54.99)", -5499),
        ("54.99-", -5499),
        ("54.99 CR", 5499),
        ("54.99 DR", -5499),
        ("54.99CR", 5499),
        ("47.00 DR", -4700),
        ("$ (1,000.00)", -100000),
        ("1,234", 123400),
        ("  -5.00 ", -500),
        ("-54.999", -5500),  # rounds to cents
        ("2.31", 231),
    ],
)
def test_parse_amount_valid(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, "abc", "12.34.56", "5 dollars", "--5"])
def test_parse_amount_invalid(raw):
    with pytest.raises(ValueError):
        parse_amount(raw)


def test_cr_suffix_beats_implicit_sign():
    assert parse_amount("54.99 CR") == 5499
    assert parse_amount("54.99 DR") == -5499
