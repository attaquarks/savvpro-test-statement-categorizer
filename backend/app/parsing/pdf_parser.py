"""Text-based PDF statement parser.

The supported PDF format is a text-based export with one transaction per
line in the form:

    YYYY-MM-DD DESCRIPTION AMOUNT

e.g. `2026-03-02  ADOBE CREATIVE CLOUD  -54.99`. Any line that does not
match (titles, column headers, page numbers) is ignored. Scanned or
image-only PDFs contain no text and are rejected with a clear message —
this parser never OCRs images.
"""

import io
import re

import pdfplumber

from .amounts import parse_amount
from .base import ParseOutcome, RawTransaction
from .dates import parse_date
from .errors import NoTransactionsError, StatementFormatError, UnsupportedFileError

_LINE = re.compile(
    r"^\s*(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<desc>.+?)\s+"
    r"(?P<amount>\(?\$?-?\d[\d,]*(?:\.\d{1,2})?\)?(?:\s*(?:CR|DR))?)\s*$",
    re.IGNORECASE,
)


def _extract_lines(data: bytes) -> list[str]:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            lines: list[str] = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.splitlines())
            return lines
    except StatementFormatError:
        raise
    except Exception as exc:
        raise StatementFormatError(f"Could not read this PDF ({exc}).") from exc


def parse_pdf(data: bytes) -> ParseOutcome:
    if b"%PDF-" not in data[:1024]:
        raise UnsupportedFileError("This file is not a valid PDF.")

    lines = _extract_lines(data)

    if not any(line.strip() for line in lines):
        raise StatementFormatError(
            "This PDF contains no extractable text — it looks like a scan. "
            "Scanned PDFs are not supported; upload a CSV or a text-based PDF."
        )

    outcome = ParseOutcome()
    for line_no, line in enumerate(lines, start=1):
        match = _LINE.match(line)
        if match is None:
            continue  # titles, column headers and footers are ignored by design

        try:
            date = parse_date(match.group("date"))
            amount_cents = parse_amount(match.group("amount"))
        except ValueError as exc:
            outcome.warnings.append(f"PDF line {line_no}: skipped ({exc}).")
            continue

        description = match.group("desc").strip()
        if not description:
            outcome.warnings.append(f"PDF line {line_no}: skipped (missing description).")
            continue

        outcome.transactions.append(
            RawTransaction(date=date, description=description, amount_cents=amount_cents)
        )

    if not outcome.transactions:
        detail = f" {len(outcome.warnings)} line(s) could not be parsed." if outcome.warnings else ""
        raise NoTransactionsError(
            "Found text in the PDF but no transaction lines. Expected one "
            "transaction per line in the format "
            "'YYYY-MM-DD DESCRIPTION AMOUNT' — see the README." + detail
        )

    return outcome
