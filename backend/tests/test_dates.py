"""Tests for date parsing and normalization to ISO."""

import pytest

from app.parsing.dates import parse_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-03-14", "2026-03-14"),  # documented primary format
        ("2026/03/14", "2026-03-14"),
        ("03/14/2026", "2026-03-14"),
        ("03/14/26", "2026-03-14"),
        ("14-Mar-2026", "2026-03-14"),
        ("14 Mar 2026", "2026-03-14"),
        ("Mar 14, 2026", "2026-03-14"),
        (" 2026-03-14 ", "2026-03-14"),
    ],
)
def test_parse_date_valid(raw, expected):
    assert parse_date(raw) == expected


def test_ambiguous_numeric_date_reads_as_month_day_year():
    assert parse_date("03/04/2026") == "2026-03-04"


@pytest.mark.parametrize("raw", ["", None, "not a date", "2026-13-40", "13/13/2026", "2026-02-30"])
def test_parse_date_invalid(raw):
    with pytest.raises(ValueError):
        parse_date(raw)
