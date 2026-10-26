"""CSV statement parser.

Primary documented format (see README):

    Date,Description,Amount
    2026-03-02,ADOBE CREATIVE CLOUD,-54.99

Amounts are signed (expenses negative, credits positive). Real bank
exports come in several shapes and all of these are supported:

- a Debit and Credit column pair instead of a signed Amount column
  (Capital One, Citi)
- a Type column (Chase) whose Debit/Credit-style values determine the
  sign of otherwise positive amounts
- a "charges are positive" convention (some American Express exports):
  charges listed positive, payments/credits negative. This cannot be
  auto-detected without guessing, so the caller selects it explicitly
  via charge_sign="positive".
- Wells Fargo-style headerless exports: Date, Amount, Check number,
  Description (the sign lives in the Amount column)
- preamble lines above the header, extra columns, `$`/`,` formatting,
  parentheses and CR/DR suffixes

Rows that cannot be parsed produce warnings and are skipped; structural
failures (no header, no usable rows, unsignable files) raise
StatementFormatError with an actionable message.
"""

import csv
import io
import re
from typing import Optional

from .amounts import parse_amount
from .base import ParseOutcome, RawTransaction
from .dates import parse_date
from .errors import EmptyFileError, NoTransactionsError, StatementFormatError

MAX_TRANSACTIONS = 20_000

DATE_ALIASES = {
    "transaction date",
    "posted date",
    "post date",
    "posting date",
    "trans date",
    "date posted",
}
DESCRIPTION_ALIASES = {
    "transaction description",
    "details",
    "detail",
    "memo",
    "name",
    "payee",
    "narrative",
    "transaction",
}
AMOUNT_ALIASES = {"amt", "value", "amount usd", "signed amount"}
DEBIT_ALIASES = {"debit amount", "money out", "withdrawal", "withdrawals"}
CREDIT_ALIASES = {"credit amount", "money in", "deposit", "deposits"}
# "DrCr" is the sign column in common Indian-bank exports (e.g. the widely
# used Kaggle bank-transaction datasets): Db = debit, Cr = credit.
TYPE_ALIASES = {"transaction type", "txn type", "drcr", "dr cr"}

# Fallback description sources: several real exports split the free text
# across two columns (e.g. name + mode / remarks / particulars). When the
# primary description cell is empty, the secondary one is used.
SECONDARY_DESCRIPTION_ALIASES = {"mode", "remarks", "narration", "particulars"}

# Header names that win over the looser aliases above. Chase credit-card
# exports carry both "Details" (a Debit/Credit column) and "Description" —
# the exact name must take priority or the description is read from the
# wrong column.
PRIMARY_ALIASES = {
    "date": {"date"},
    "description": {"description"},
    "amount": {"amount"},
    "debit": {"debit"},
    "credit": {"credit"},
    "type": {"type"},
}

# Type-column values whose wording definitively says which side of the
# statement the money is on. "payment" is deliberately absent: on a card
# statement it is a credit, on a checking statement it is often a debit.
CREDIT_TYPE_WORDS = {"CREDIT", "CR", "CRT", "DEPOSIT", "REFUND", "RETURN"}
DEBIT_TYPE_WORDS = {"DEBIT", "DR", "DB", "DBT", "WITHDRAWAL", "PURCHASE", "SALE", "CHARGE", "FEE", "FEES"}


def sign_from_type(value: str) -> Optional[int]:
    """Map a Type column value to +1 (credit) / -1 (debit) / None (unknown)."""
    tokens = {token for token in re.split(r"[^A-Z]+", str(value).upper()) if token}
    if tokens & CREDIT_TYPE_WORDS:
        return 1
    if tokens & DEBIT_TYPE_WORDS:
        return -1
    return None


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
    return re.sub(r"[^a-z0-9]+", " ", cell.lower()).strip()


def _find_column(header: list[str], *alias_sets: set[str]) -> Optional[int]:
    """Find a column, trying exact primary names before looser aliases."""
    for aliases in alias_sets:
        for index, cell in enumerate(header):
            if cell in aliases:
                return index
    return None


def _find_header(rows: list[list[str]]):
    """Locate the header row within the first rows of the file.

    Returns (header_index, column_map). The map points at the date,
    description, amount (or debit/credit pair) and optional type column.
    """
    for idx, row in enumerate(rows[:15]):
        header = [_normalize_header(cell) for cell in row]
        if not any(header):
            continue
        date_col = _find_column(header, PRIMARY_ALIASES["date"], DATE_ALIASES)
        desc_col = _find_column(header, PRIMARY_ALIASES["description"], DESCRIPTION_ALIASES)
        amount_col = _find_column(header, PRIMARY_ALIASES["amount"], AMOUNT_ALIASES)
        debit_col = _find_column(header, PRIMARY_ALIASES["debit"], DEBIT_ALIASES)
        credit_col = _find_column(header, PRIMARY_ALIASES["credit"], CREDIT_ALIASES)
        type_col = _find_column(header, PRIMARY_ALIASES["type"], TYPE_ALIASES)
        if date_col is None or desc_col is None:
            continue
        if amount_col is None and (debit_col is None or credit_col is None):
            continue
        return idx, {
            "date": date_col,
            "description": desc_col,
            "secondary_description": _find_column(header, SECONDARY_DESCRIPTION_ALIASES),
            "amount": amount_col,
            "debit": debit_col,
            "credit": credit_col,
            "type": type_col,
        }
    return None, None


def _cell(row: list[str], col: Optional[int]) -> str:
    if col is None or col >= len(row):
        return ""
    return row[col].strip()


def _unsigned_amount_file_message() -> str:
    return (
        "Every amount in this file is positive, so expenses and credits cannot be "
        "told apart. Upload a layout with sign information: signed amounts "
        "(expenses negative), separate Debit/Credit columns, a Type column with "
        "Debit/Credit values (e.g. Chase exports) — or re-upload with 'Charges are "
        "positive' selected if your bank lists charges as positive amounts (e.g. "
        "some American Express exports). See the README."
    )


def _try_headerless(
    rows: list[list[str]], charge_sign: str, warnings: list[str]
) -> Optional[ParseOutcome]:
    """Parse Wells Fargo-style headerless rows: Date, Amount, ..., Description.

    Only commits when every non-empty row matches the shape (first cell a
    date, second an amount, at least three cells) — otherwise returns None
    so the normal 'no header' error fires.
    """
    for row in rows:
        if not any(cell.strip() for cell in row):
            continue
        if len(row) < 3:
            return None
        try:
            parse_date(row[0].strip())
            parse_amount(row[1].strip())
        except ValueError:
            return None

    outcome = ParseOutcome()
    for row_idx, row in enumerate(rows, start=1):
        if not any(cell.strip() for cell in row):
            continue
        try:
            date = parse_date(row[0].strip())
            amount_cents = parse_amount(row[1].strip())
        except ValueError as exc:
            warnings.append(f"Row {row_idx}: skipped ({exc}).")
            continue
        description = row[-1].strip()
        if not description:
            warnings.append(f"Row {row_idx}: skipped (missing description).")
            continue
        if charge_sign == "positive":
            amount_cents = -amount_cents
        outcome.transactions.append(
            RawTransaction(date=date, description=description, amount_cents=amount_cents)
        )

    if outcome.transactions:
        return outcome
    return None


def parse_csv(data: bytes, charge_sign: str = "negative") -> ParseOutcome:
    """Parse a CSV statement.

    charge_sign only applies to files whose sign comes from the Amount
    column itself: "negative" (default, documented) means expenses are
    negative in the file; "positive" means charges are listed positive
    (some American Express exports). Debit/Credit columns and Type
    columns are authoritative and ignore charge_sign.
    """
    if not data.strip():
        raise EmptyFileError("The uploaded CSV file is empty.")

    text = _decode(data)
    delimiter = _sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]

    header_idx, cols = _find_header(rows)
    if header_idx is None:
        outcome = _try_headerless(rows, charge_sign, warnings := [])
        if outcome is None:
            sample = ", ".join(rows[0]) if rows else "(file has no rows)"
            raise StatementFormatError(
                "Could not find a header row with Date, Description and Amount "
                f"columns (or Debit/Credit columns). First row was: {sample}. "
                "If this is a Wells Fargo-style headerless export it must be "
                "Date, Amount, ..., Description — see the README."
            )
        return outcome

    if header_idx > 0:
        skipped = [row for row in rows[:header_idx] if any(cell.strip() for cell in row)]
        if skipped:
            outcome_warnings = [
                f"Ignored {len(skipped)} preamble line(s) before the header row."
            ]
    else:
        outcome_warnings = []

    outcome = ParseOutcome(warnings=outcome_warnings)
    used_type_sign = False

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
            description = _cell(row, cols["secondary_description"])
        if not description:
            problems.append("missing description")

        amount_cents = None
        amount_raw = _cell(row, cols["amount"])
        debit_raw = _cell(row, cols["debit"])
        credit_raw = _cell(row, cols["credit"])
        type_raw = _cell(row, cols["type"])

        if cols["amount"] is not None:
            try:
                amount_cents = parse_amount(amount_raw)
            except ValueError as exc:
                problems.append(str(exc))

            # A Type column (e.g. Chase exports) is authoritative when its
            # value is recognizable; unrecognized values keep the raw sign.
            if problems == [] and cols["type"] is not None and type_raw:
                type_sign = sign_from_type(type_raw)
                if type_sign is not None:
                    amount_cents = type_sign * abs(amount_cents)
                    used_type_sign = True
                elif charge_sign == "positive":
                    amount_cents = -amount_cents
            elif problems == [] and charge_sign == "positive":
                amount_cents = -amount_cents
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

    # Mixed-sign files billed with the opposite convention (charges positive,
    # e.g. some American Express exports) cannot be auto-detected without
    # guessing — but refund/payment lines with negative amounts are a strong
    # tell. Warn instead of failing, so signed files keep working.
    if charge_sign == "negative":
        inverted_tells = [
            txn
            for txn in outcome.transactions
            if txn.amount_cents < 0
            and (
                "REFUND" in txn.description.upper()
                or "PAYMENT RECEIVED" in txn.description.upper()
            )
        ]
        if inverted_tells:
            outcome.warnings.append(
                "Negative amounts appear on refund/payment lines — this file may "
                "list charges as positive (e.g. some American Express exports). If "
                "the categories look inverted, re-upload with 'Charges are "
                "positive' selected."
            )

    positive_only = all(t.amount_cents > 0 for t in outcome.transactions)
    if (
        positive_only
        and len(outcome.transactions) >= 2
        and charge_sign == "negative"
        and not used_type_sign
        and cols["amount"] is not None
        and cols["debit"] is None
    ):
        raise StatementFormatError(_unsigned_amount_file_message())

    return outcome
