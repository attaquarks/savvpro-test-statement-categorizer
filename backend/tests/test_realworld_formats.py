"""Tests against real-world bank export layouts.

The fixtures under tests/fixtures/realworld/ mirror the documented CSV
export formats of major US banks (Chase, American Express, Capital One,
Wells Fargo), filled with invented, fake transaction data. Real bank
statements or personal details are never committed.
"""

from pathlib import Path

import pytest

from app import categories as cat
from app.categorizer import categorize_statement
from app.parsing.csv_parser import parse_csv, sign_from_type
from app.parsing.errors import StatementFormatError

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "realworld"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _parse(name: str, **kwargs):
    return categorize_statement(parse_csv(_fixture(name).encode("utf-8"), **kwargs))


def _by_description(transactions, needle):
    for txn in transactions:
        if needle in txn.description.upper():
            return txn
    raise AssertionError(f"no transaction containing {needle!r}")


# --- Type column word mapping ------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("DEBIT", -1),
        ("DEBIT CARD PURCHASE", -1),
        ("ACH_DEBIT", -1),
        ("WITHDRAWAL", -1),
        ("FEES", -1),
        ("CREDIT", 1),
        ("ACH CREDIT", 1),
        ("DEPOSIT", 1),
        ("RETURN", 1),
        ("REFUND", 1),
        ("CHECK", None),  # a check can go either way — never guessed
        ("PAYMENT", None),  # card-vs-checking direction differs — never guessed
        ("ADJUSTMENT", None),
    ],
)
def test_sign_from_type(value, expected):
    assert sign_from_type(value) == expected


# --- Chase layout: signed amounts + Type column -------------------------------


def test_chase_style_signed_amounts_are_unchanged():
    transactions = _parse("chase_style.csv")
    adobe = _by_description(transactions, "ADOBE CREATIVE CLOUD")
    assert adobe.amount_cents == -5499
    assert adobe.category == cat.SOFTWARE

    # A Type=CREDIT row whose raw amount is negative becomes a credit, and an
    # unrecognized card payment honestly needs review instead of being guessed.
    payment = _by_description(transactions, "PAYMENT THANK YOU")
    assert payment.amount_cents == 20000
    assert payment.category == cat.NEEDS_REVIEW


def test_chase_style_return_type_refund_is_detected():
    transactions = _parse("chase_style.csv")
    refund = _by_description(transactions, "REFUND ADOBE")
    assert refund.category == cat.REFUND
    assert refund.refund_category == cat.SOFTWARE


# --- Type column with all-positive amounts ------------------------------------


def test_type_column_positive_amounts_derive_their_sign():
    transactions = _parse("type_column_positive.csv")
    assert _by_description(transactions, "ADOBE").amount_cents == -5499
    assert _by_description(transactions, "INVOICE PAYMENT").category == cat.INCOME
    assert _by_description(transactions, "TRANSFER TO BUSINESS").category == cat.TRANSFER
    assert _by_description(transactions, "MONTHLY SERVICE FEE").category == cat.FEES
    assert _by_description(transactions, "JOES CAFE").category == cat.NEEDS_REVIEW


def test_all_positive_type_column_file_is_accepted():
    # The file's raw amounts are all positive; the Type column resolves them.
    # Regression test: real exports of this shape were rejected before.
    transactions = _parse("type_column_positive.csv")
    assert len(transactions) == 7


def test_unrecognized_type_values_with_only_positive_amounts_are_rejected():
    with pytest.raises(StatementFormatError) as excinfo:
        parse_csv(_fixture("type_column_unknown.csv").encode("utf-8"))
    assert "positive" in str(excinfo.value)
    assert "Charges are positive" in str(excinfo.value)


def test_mixed_type_recognition_keeps_raw_sign_for_unclear_rows():
    content = (
        "Date,Description,Type,Amount\n"
        "2026-03-01,STAPLES CREDIT ACP,DEBIT,5.00\n"
        "2026-03-02,CHECK 1042,WIRED,7.00\n"
    )
    outcome = parse_csv(content.encode("utf-8"))
    assert [t.amount_cents for t in outcome.transactions] == [-500, 700]


# --- American Express layout: charges positive, credits negative --------------


def test_amex_style_rejected_or_warned_by_default_and_fixed_with_charge_sign():
    # All-positive amex-style files are rejected rather than flipped by guess;
    # mixed-sign amex-style files parse with a warning pointing at the option.
    mixed = parse_csv(_fixture("amex_style_positive_charges.csv").encode("utf-8"))
    assert any("Charges are positive" in w for w in mixed.warnings)

    # With the explicit option the signs invert correctly: charges become
    # debits, payments become credits, and the suspicion warning disappears.
    transactions = _parse("amex_style_positive_charges.csv", charge_sign="positive")
    adobe = _by_description(transactions, "ADOBE CREATIVE CLOUD")
    assert adobe.amount_cents == -5499
    assert adobe.category == cat.SOFTWARE

    payment = _by_description(transactions, "PAYMENT RECEIVED")
    assert payment.amount_cents == 20000

    refund = _by_description(transactions, "REFUND ADOBE")
    assert refund.amount_cents == 5499
    assert refund.refund_category == cat.SOFTWARE


def test_charge_sign_positive_flips_signed_files_consistently():
    outcome = parse_csv(
        b"Date,Description,Amount\n2026-03-01,STAPLES,-5.00\n2026-03-02,STARBUCKS,-6.00\n",
        charge_sign="positive",
    )
    assert [t.amount_cents for t in outcome.transactions] == [500, 600]


# --- Capital One layout: Debit/Credit pair -------------------------------------


def test_capital_one_style_debit_credit_columns():
    transactions = _parse("capital_one_style.csv")
    assert _by_description(transactions, "ADOBE").amount_cents == -5499
    assert _by_description(transactions, "DELTA").category == cat.TRAVEL
    assert _by_description(transactions, "PAYMENT RECEIVED").amount_cents == 20000


# --- Wells Fargo layout: headerless Date, Amount, ..., Description -------------


def test_wells_fargo_style_headerless_export_parses():
    transactions = _parse("wells_fargo_style_headerless.csv")
    assert [t.amount_cents for t in transactions] == [
        -5499,
        240000,
        -2345,
        -200000,
        -1850,
        5499,
    ]
    assert _by_description(transactions, "INVOICE PAYMENT").category == cat.INCOME
    assert _by_description(transactions, "TRANSFER TO BUSINESS").category == cat.TRANSFER
    assert _by_description(transactions, "REFUND").refund_category == cat.SOFTWARE


def test_headerless_fallback_requires_date_and_amount_shape():
    with pytest.raises(StatementFormatError):
        parse_csv(b"first,line,looks,nothing,like,dates\nsecond,line,also,not\n")
