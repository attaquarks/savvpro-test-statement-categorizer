"""CSV statement parser.

The documented CSV format (see README) is:

    Date,Description,Amount
    2026-03-02,ADOBE CREATIVE CLOUD,-54.99

Amounts are signed (expenses negative, credits positive). Two export
styles are also tolerated:

- separate Debit and Credit columns instead of a signed Amount column
- a preamble above the header row and extra columns, which are ignored

Rows that cannot be parsed produce warnings and are skipped; structural
failures (no header, no usable rows) raise StatementFormatError.
"""

import csv
import io
from typing import Optional

from .amounts import parse_amount
from .base import ParseOutcome, RawTransaction
from .dates import parse_date
from .errors import EmptyFileError, NoTransactionsError, StatementFormatError

MAX_TRANSACTIONS = 20_000

DATE_ALIASES = {
    "date",
    "transaction date",
    "posted date",
    "post date",
    "posting date",
    "trans date",
    "date posted",
}
DESCRIPTION_ALIASES = {
    "description",
    "transaction description",
    "details",
    "detail",
    "memo",
    "name",
    "payee",
    "narrative",
    "transaction",
}
AMOUNT_ALIASES = {"amount", "amt", "value", "amount usd", "signed amount"}
DEBIT_ALIASES = {"debit", "debit amount", "money out", "withdrawal", "withdrawals"}
CREDIT_ALIASES = {"credit", "credit amount", "money in", "deposit", "deposits"}


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _sniff_delimiter(text: str) -> str:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def _normalize_header(cell: str) -> str:
    return " ".join(cell.split()).strip().lower()


def _find_column(header: list[str], aliases: set[str]) -> Optional[int]:
    for index, cell in enumerate(header):
        if cell in aliases:
            return index
    return None


def _find_header(rows: list[list[str]]):
    """Locate the header row within the first rows of the file.

    Returns (header_index, column_map). Column_map maps logical names to
    column indexes; date and description are required plus either an
    amount column or both debit and credit columns.
    """
    for idx, row in enumerate(rows[:15]):
        header = [_normalize_header(cell) for cell in row]
        if not any(header):
            continue
        date_col = _find_column(header, DATE_ALIASES)
        desc_col = _find_column(header, DESCRIPTION_ALIASES)
        amount_col = _find_column(header, AMOUNT_ALIASES)
        debit_col = _find_column(header, DEBIT_ALIASES)
        credit_col = _find_column(header, CREDIT_ALIASES)
        if date_col is None or desc_col is None:
            continue
        if amount_col is None and (debit_col is None or credit_col is None):
            continue
        return idx, {
            "date": date_col,
            "description": desc_col,
            "amount": amount_col,
            "debit": debit_col,
            "credit": credit_col,
        }
    return None, None


def _cell(row: list[str], col: Optional[int]) -> str:
    if col is None or col >= len(row):
        return ""
    return row[col].strip()


def parse_csv(data: bytes) -> ParseOutcome:
    if not data.strip():
        raise EmptyFileError("The uploaded CSV file is empty.")

    text = _decode(data)
    delimiter = _sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]

    header_idx, cols = _find_header(rows)
    if header_idx is None:
        sample = ", ".join(rows[0]) if rows else "(file has no rows)"
        raise StatementFormatError(
            "Could not find a header row with Date, Description and Amount "
            f"columns (or Debit/Credit columns). First row was: {sample}. "
            "See the documented statement format in the README."
        )

    if header_idx > 0:
        skipped = [row for row in rows[:header_idx] if any(cell.strip() for cell in row)]
        if skipped:
            outcome_warnings = [
                f"Ignored {len(skipped)} preamble line(s) before the header row."
            ]
    else:
        outcome_warnings = []

    outcome = ParseOutcome(warnings=outcome_warnings)

    for row_idx in range(header_idx + 1, len(rows)):
        row = rows[row_idx]
        file_row = row_idx + 1

        if len(outcome.transactions) >= MAX_TRANSACTIONS:
            raise StatementFormatError(
                f"This statement exceeds the {MAX_TRANSACTIONS:,} transaction limit."
            )

        problems = []

        date_raw = _cell(row, cols["date"])
        try:
            date = parse_date(date_raw)
        except ValueError as exc:
            problems.append(str(exc))
            date = None

        description = _cell(row, cols["description"])
        if not description:
            problems.append("missing description")

        amount_cents = None
        amount_raw = _cell(row, cols["amount"])
        debit_raw = _cell(row, cols["debit"])
        credit_raw = _cell(row, cols["credit"])

        if cols["amount"] is not None:
            try:
                amount_cents = parse_amount(amount_raw)
            except ValueError as exc:
                problems.append(str(exc))
        else:
            has_debit = bool(debit_raw)
            has_credit = bool(credit_raw)
            if has_debit and has_credit:
                problems.append("row has both a debit and a credit value")
            elif has_debit:
                try:
                    amount_cents = -abs(parse_amount(debit_raw))
                except ValueError as exc:
                    problems.append(f"debit column: {exc}")
            elif has_credit:
                try:
                    amount_cents = abs(parse_amount(credit_raw))
                except ValueError as exc:
                    problems.append(f"credit column: {exc}")
            else:
                problems.append("no amount in debit or credit column")

        if problems:
            outcome.warnings.append(f"Row {file_row}: skipped ({'; '.join(problems)}).")
            continue

        assert date is not None and amount_cents is not None
        outcome.transactions.append(
            RawTransaction(date=date, description=description, amount_cents=amount_cents)
        )

    if not outcome.transactions:
        detail = f" {len(outcome.warnings)} row(s) were skipped." if outcome.warnings else ""
        raise NoTransactionsError(
            "No usable transactions were found below the header row." + detail
        )

    positive_only = all(t.amount_cents > 0 for t in outcome.transactions)
    if positive_only and len(outcome.transactions) >= 2:
        raise StatementFormatError(
            "Every amount in this file is positive. The documented format expects "
            "signed amounts (expenses negative) or separate Debit/Credit columns; "
            "otherwise expenses and credits cannot be told apart. See the README."
        )

    return outcome
