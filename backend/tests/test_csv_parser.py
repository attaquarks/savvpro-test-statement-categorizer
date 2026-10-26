"""Tests for the CSV statement parser."""

import pytest

from app.parsing.base import RawTransaction
from app.parsing.csv_parser import parse_csv
from app.parsing.errors import (
    EmptyFileError,
    NoTransactionsError,
    StatementFormatError,
)


def _parse(text: str):
    return parse_csv(text.encode("utf-8"))


def test_documented_format_parses_signed_amounts():
    outcome = _parse(
        "Date,Description,Amount\n"
        "2026-03-02,ADOBE CREATIVE CLOUD,-54.99\n"
        "2026-03-02,INVOICE PAYMENT ACME CORP,2400.00\n"
    )
    assert outcome.transactions == [
        RawTransaction("2026-03-02", "ADOBE CREATIVE CLOUD", -5499),
        RawTransaction("2026-03-02", "INVOICE PAYMENT ACME CORP", 240000),
    ]
    assert outcome.warnings == []


def test_debit_credit_columns_become_signed_amounts():
    outcome = _parse(
        "Date,Description,Debit,Credit\n"
        "2026-03-01,STAPLES CREDIT ACP,5.00,\n"
        "2026-03-02,REFUND STAPLES,,5.00\n"
    )
    assert [t.amount_cents for t in outcome.transactions] == [-500, 500]


def test_extra_columns_are_ignored():
    outcome = _parse(
        "Date,Description,Type,Balance,Amount\n"
        '2026-03-01,STAPLES,BUY,1000.00,"-5.00"\n'
    )
    assert len(outcome.transactions) == 1
    assert outcome.transactions[0].amount_cents == -500


def test_bom_and_crlf_are_tolerated():
    data = (
        b"\xef\xbb\xbfDate,Description,Amount\r\n"
        b"2026-03-01,STAPLES,-5.00\r\n"
    )
    outcome = parse_csv(data)
    assert outcome.transactions[0].description == "STAPLES"


def test_preamble_before_header_is_ignored_with_warning():
    outcome = _parse(
        "WESTBANK BUSINESS CARD\n"
        "Account 1234 (sample)\n"
        "Date,Description,Amount\n"
        "2026-03-01,STAPLES,-5.00\n"
    )
    assert len(outcome.transactions) == 1
    assert any("preamble" in w for w in outcome.warnings)


def test_semicolon_delimiter_is_detected():
    outcome = _parse("Date;Description;Amount\n2026-03-01;STAPLES;-5.00\n")
    assert outcome.transactions[0].amount_cents == -500


def test_bad_rows_become_warnings_and_parsing_continues():
    outcome = _parse(
        "Date,Description,Amount\n"
        "2026-03-01,GOOD MERCHANT,-5.00\n"
        "2026-03-02,BAD AMOUNT ROW,abc\n"
        "03/32/2026,BAD DATE ROW,-1.00\n"
        "2026-03-04,GOOD AGAIN,-7.00\n"
    )
    assert [t.description for t in outcome.transactions] == ["GOOD MERCHANT", "GOOD AGAIN"]
    assert len(outcome.warnings) == 2
    assert "Row 3" in outcome.warnings[0]
    assert "Row 4" in outcome.warnings[1]


def test_row_with_both_debit_and_credit_is_skipped_with_warning():
    outcome = _parse(
        "Date,Description,Debit,Credit\n"
        "2026-03-01,GOOD,5.00,\n"
        "2026-03-02,CONFUSED ROW,5.00,5.00\n"
    )
    assert len(outcome.transactions) == 1
    assert any("both a debit and a credit" in w for w in outcome.warnings)


def test_missing_description_is_skipped_with_warning():
    outcome = _parse(
        "Date,Description,Amount\n"
        "2026-03-01,,-5.00\n"
        "2026-03-02,GOOD,-1.00\n"
    )
    assert len(outcome.transactions) == 1
    assert any("missing description" in w for w in outcome.warnings)


def test_empty_file_raises():
    with pytest.raises(EmptyFileError):
        parse_csv(b"")
    with pytest.raises(EmptyFileError):
        parse_csv(b"   \n  ")


def test_no_recognizable_header_raises():
    with pytest.raises(StatementFormatError) as excinfo:
        _parse("Foo,Bar,Baz\n1,2,3\n")
    assert "header row" in str(excinfo.value)


def test_header_without_amount_columns_raises():
    with pytest.raises(StatementFormatError):
        _parse("Date,Description\n2026-03-01,STAPLES\n")


def test_header_only_file_has_no_transactions():
    with pytest.raises(NoTransactionsError):
        _parse("Date,Description,Amount\n")


def test_all_rows_bad_yields_no_transactions():
    with pytest.raises(NoTransactionsError) as excinfo:
        _parse("Date,Description,Amount\n2026-03-01,A,abc\n2026-03-02,B,xyz\n")
    assert "2 row(s) were skipped" in str(excinfo.value)


def test_all_positive_amounts_are_rejected_as_likely_unsigned():
    with pytest.raises(StatementFormatError) as excinfo:
        _parse(
            "Date,Description,Amount\n"
            "2026-03-01,STAPLES,5.00\n"
            "2026-03-02,STARBUCKS,6.00\n"
        )
    assert "signed" in str(excinfo.value)


def test_quoted_descriptions_with_commas_parse():
    outcome = _parse(
        'Date,Description,Amount\n'
        '2026-03-01,"CAFE X, MAIN ST",-4.00\n'
    )
    assert outcome.transactions[0].description == "CAFE X, MAIN ST"
