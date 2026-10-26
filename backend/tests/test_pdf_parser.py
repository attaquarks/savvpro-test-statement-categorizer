"""Tests for the text-based PDF statement parser."""

import pytest
from fpdf import FPDF

from app.parsing.errors import (
    NoTransactionsError,
    StatementFormatError,
    UnsupportedFileError,
)
from app.parsing.pdf_parser import parse_pdf


def _make_pdf(lines: list[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("courier", size=10)
    for line in lines:
        pdf.cell(0, 12, text=line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def test_parses_transactions_and_ignores_other_lines():
    data = _make_pdf(
        [
            "WESTBANK BUSINESS CARD - FAKE SAMPLE STATEMENT",
            "Date        Description                    Amount",
            "2026-03-02  ADOBE CREATIVE CLOUD           -54.99",
            "2026-03-02  INVOICE PAYMENT ACME CORP      2400.00",
            "Page 1 of 2",
        ]
    )
    outcome = parse_pdf(data)
    assert len(outcome.transactions) == 2
    assert outcome.transactions[0].description == "ADOBE CREATIVE CLOUD"
    assert outcome.transactions[0].amount_cents == -5499
    assert outcome.transactions[1].amount_cents == 240000
    assert outcome.warnings == []


def test_invalid_transaction_line_becomes_warning():
    data = _make_pdf(
        [
            "2026-13-99  BAD DATE ROW  -5.00",
            "2026-03-02  GOOD ROW  -1.00",
        ]
    )
    outcome = parse_pdf(data)
    assert len(outcome.transactions) == 1
    assert outcome.transactions[0].description == "GOOD ROW"
    assert len(outcome.warnings) == 1
    assert "PDF line 1" in outcome.warnings[0]


def test_pdf_without_transaction_lines_raises():
    data = _make_pdf(["WESTBANK BUSINESS CARD", "Page 1 of 1"])
    with pytest.raises(NoTransactionsError):
        parse_pdf(data)


def test_pdf_without_extractable_text_raises():
    # A page with no text at all behaves like a scan.
    data = _make_pdf([])
    with pytest.raises(StatementFormatError) as excinfo:
        parse_pdf(data)
    assert "no extractable text" in str(excinfo.value)


def test_non_pdf_bytes_are_rejected():
    with pytest.raises(UnsupportedFileError):
        parse_pdf(b"GIF89a not a pdf at all")


def test_corrupt_pdf_with_magic_bytes_raises_format_error():
    with pytest.raises(StatementFormatError):
        parse_pdf(b"%PDF-1.7 this is not really a pdf body")
