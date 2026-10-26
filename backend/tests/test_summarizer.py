"""Tests for the summary math: refunds, transfers, income, overrides."""

from app import categories as cat
from app.models import Transaction
from app.summarizer import build_summary

REFUNDS_UNMATCHED = "Refunds (unmatched)"


def _txn(txn_id, amount_cents, category, **extra):
    return Transaction(
        id=txn_id,
        date="2026-03-01",
        description=extra.pop("description", txn_id),
        amount_cents=amount_cents,
        category=category,
        **extra,
    )


def _by_category(summary, name):
    for row in summary.by_category:
        if row.category == name:
            return row
    return None


def test_empty_transactions_yield_zeroed_summary():
    summary = build_summary([])
    assert summary.transaction_count == 0
    assert summary.total_spending_cents == 0
    assert summary.total_income_cents == 0
    assert summary.needs_review_count == 0
    assert summary.by_category == []


def test_refund_offsets_its_category_and_is_not_income():
    summary = build_summary(
        [
            _txn("t1", -5499, cat.SOFTWARE, description="ADOBE"),
            _txn("t2", 5499, cat.REFUND, refund_category=cat.SOFTWARE, description="REFUND ADOBE"),
            _txn("t3", 240000, cat.INCOME, description="INVOICE PAYMENT"),
        ]
    )
    software = _by_category(summary, cat.SOFTWARE)
    assert software.spending_cents == 5499
    assert software.refunds_cents == 5499
    assert software.net_cents == 0
    # Refund must not appear in income.
    assert summary.total_income_cents == 240000
    assert summary.total_refunds_cents == 5499
    assert summary.net_spending_cents == 0


def test_transfers_are_excluded_from_spending_and_income():
    summary = build_summary(
        [
            _txn("t1", -200000, cat.TRANSFER),
            _txn("t2", 150000, cat.TRANSFER),
            _txn("t3", -5499, cat.SOFTWARE),
        ]
    )
    assert summary.transfers_out_cents == 200000
    assert summary.transfers_in_cents == 150000
    assert summary.transfers_count == 2
    assert summary.total_spending_cents == 5499
    assert summary.total_income_cents == 0


def test_needs_review_rows_are_held_out_of_totals():
    summary = build_summary(
        [
            _txn("t1", -8642, cat.NEEDS_REVIEW),
            _txn("t2", 25000, cat.NEEDS_REVIEW),
            _txn("t3", -500, cat.MEALS),
        ]
    )
    assert summary.needs_review_count == 2
    assert summary.needs_review_amount_cents == 8642 + 25000
    assert summary.total_spending_cents == 500


def test_unmatched_refund_is_reported_separately():
    summary = build_summary([_txn("t1", 5499, cat.REFUND)])
    assert summary.total_refunds_cents == 5499
    row = _by_category(summary, REFUNDS_UNMATCHED)
    assert row is not None
    assert row.refunds_cents == 5499
    assert row.net_cents == -5499


def test_credit_in_a_spending_category_offsets_it():
    # A user put a credit into a spending category: treat as a refund of it.
    summary = build_summary(
        [
            _txn("t1", -5499, cat.SOFTWARE),
            _txn("t2", 1000, cat.SOFTWARE, source="user"),
        ]
    )
    row = _by_category(summary, cat.SOFTWARE)
    assert row.spending_cents == 5499
    assert row.refunds_cents == 1000
    assert row.net_cents == 4499


def test_user_override_moves_money_between_buckets():
    # A needs-review expense re-categorized as a transfer stops counting.
    summary = build_summary(
        [
            _txn("t1", -25000, cat.TRANSFER, source="user"),
            _txn("t2", -1850, cat.NEEDS_REVIEW),
        ]
    )
    assert summary.total_spending_cents == 0
    assert summary.transfers_out_cents == 25000
    assert summary.needs_review_count == 1
    assert summary.needs_review_amount_cents == 1850


def test_unknown_category_string_is_treated_as_needs_review():
    summary = build_summary([_txn("t1", -500, "Mystery Bucket")])
    assert summary.needs_review_count == 1
    assert summary.needs_review_amount_cents == 500


def test_by_category_rows_are_sorted_by_net_spending():
    summary = build_summary(
        [
            _txn("t1", -100, cat.MEALS),
            _txn("t2", -900, cat.SOFTWARE),
            _txn("t3", -500, cat.TRAVEL),
        ]
    )
    nets = [row.net_cents for row in summary.by_category]
    assert nets == sorted(nets, reverse=True)
    assert summary.by_category[0].category == cat.SOFTWARE


def test_category_transaction_count_includes_refund_rows():
    summary = build_summary(
        [
            _txn("t1", -5499, cat.SOFTWARE),
            _txn("t2", 5499, cat.REFUND, refund_category=cat.SOFTWARE),
        ]
    )
    assert _by_category(summary, cat.SOFTWARE).transaction_count == 2
