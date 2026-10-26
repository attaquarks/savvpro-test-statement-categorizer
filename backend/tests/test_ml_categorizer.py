"""Focused tests for the ML tier in the categorization engine.

The tier must only ever ADD auto-categorizations on debits whose wording
the keyword tiers miss; semantics (transfers, refunds, card payments) and
uncertainty behavior must stay exactly as before.
"""

import pytest

from app import categories as cat
from app.categorizer import engine, ml


@pytest.fixture(scope="module", autouse=True)
def trained_classifier():
    model = ml.get_classifier()
    if model is None:
        pytest.skip("scikit-learn unavailable or no trainable labeled data")
    return model


def test_known_merchants_still_rule_categorized():
    for description, expected in [
        ("ADOBE CREATIVE CLOUD", cat.SOFTWARE),
        ("STARBUCKS STORE 9921", cat.MEALS),
        ("UBER *TRIP HELP.UBER.COM", cat.TRAVEL),
        ("BEST BUY #08812", cat.HARDWARE),
        ("STAPLES CREDIT CENTER", cat.OFFICE_SUPPLIES),
        ("GOOGLE ADS 81204", cat.ADVERTISING),
    ]:
        result = engine.classify(description, -4999)
        assert result.category == expected, description
        assert result.needs_review is False
        assert result.method is None  # decided by keyword tier, not the model


def test_noisy_descriptions_categorized_without_exact_match():
    # Reference numbers, odd casing, extra wording — none of these strings
    # contain a contiguous keyword from the rule tables, so only the text
    # model can place them.
    for description, expected in [
        ("microsoft corporation renewal 9988123", cat.SOFTWARE),
        ("delta airlines tkt 016441 8812", cat.TRAVEL),
    ]:
        result = engine.classify(description, -2499)
        assert result.needs_review is False, description
        assert result.category == expected, f"{description} -> {result.category}"
        assert result.method == "ml", description
        assert result.confidence is not None and result.confidence >= ml.MIN_SCORE
        assert result.confidence <= 1.0

    # Punctuation / reference noise on a rule-covered merchant is still
    # handled by the keyword tier (normalization strips the noise).
    punctuated = engine.classify("SQ *UDEMY ONLINE COURSE 778812", -2499)
    assert punctuated.category == cat.EDUCATION
    assert punctuated.method is None
    assert punctuated.needs_review is False


def test_predictions_below_the_gate_stay_in_review():
    # The model ranks this Software but below the 0.65 gate (validation
    # showed raising the gate is safer than auto-categorizing 0.5-ish rows).
    below_gate = engine.classify("creative cloud monthly subscription ref 450199348", -2499)
    assert below_gate.needs_review is True
    assert below_gate.category == cat.NEEDS_REVIEW
    assert below_gate.method is None


def test_normalized_descriptions_match_the_same_way():
    messy = "  ADOBE !!   CREATIVE   CLOUD ref# 000451 "
    clean = "ADOBE CREATIVE CLOUD"
    # Same category, still rule-decided despite punctuation/whitespace noise.
    assert engine.classify(messy, -2999).category == engine.classify(clean, -2999).category
    assert engine.classify(messy, -2999).method is None


def test_unfamiliar_descriptions_still_need_review():
    for description in ["JOES CAFE 9921", "TOTALLY UNHEARD MERCHANT XYZ", "bright lane laundry"]:
        result = engine.classify(description, -1899)
        assert result.needs_review is True, description
        assert result.category == cat.NEEDS_REVIEW
        assert result.method is None


def test_threshold_gate_sends_weak_predictions_to_review(monkeypatch):
    description = "microsoft corporation renewal 9988123"
    baseline = engine.classify(description, -2499)
    assert baseline.needs_review is False  # passes the default gates

    monkeypatch.setattr(ml, "MIN_SCORE", 1.01)
    gated = engine.classify(description, -2499)
    assert gated.needs_review is True
    assert gated.method is None


def test_transfers_refunds_and_card_payments_keep_semantics():
    assert engine.classify("TRANSFER TO SAVINGS 7734", -50000).category == cat.TRANSFER
    credit_card_payment = engine.classify("CREDIT CARD PAYMENT THANK YOU", 80000)
    assert credit_card_payment.category == cat.TRANSFER

    refund_without_merchant = engine.classify("REFUND OF PURCHASE", 2500)
    assert refund_without_merchant.needs_review is True  # never counted as income

    merchant_refund = engine.classify("STARBUCKS STORE 9921 REFUND", 4999)
    assert merchant_refund.category == cat.REFUND
    assert merchant_refund.refund_category == cat.MEALS

    assert engine.classify("PAYROLL DEPOSIT ACME CORP", 250000).category == cat.INCOME


def test_ml_never_touches_credits():
    # Even wording that strongly resembles a spending merchant must not turn
    # a credit into a spending category; it is a refund (or review), rules-decided.
    result = engine.classify("creative cloud monthly subscription ref 450199348", 2499)
    assert result.category in (cat.REFUND, cat.NEEDS_REVIEW)
    assert result.method is None
    assert result.category != cat.SOFTWARE


def test_empty_and_whitespace_descriptions_do_not_crash():
    for description in ["", "   ", "---"]:
        result = engine.classify(description, -1000)
        assert result.needs_review is True
        assert result.category == cat.NEEDS_REVIEW


def test_suggest_is_none_without_trained_model(monkeypatch):
    monkeypatch.setattr(ml, "_build_attempted", True)
    monkeypatch.setattr(ml, "_classifier", None)
    assert ml.suggest("creative cloud monthly subscription") is None
    assert ml.suggest("") is None


def test_build_training_examples_are_valid_and_deduplicated():
    examples = ml.build_training_examples()
    descriptions = [d for d, _ in examples]
    assert len(descriptions) == len(set(descriptions))
    assert all(c in cat.SPENDING_SET for _, c in examples)


def test_transaction_model_carries_confidence_and_method():
    from app.models import Transaction

    row = Transaction(
        id="txn-0001",
        date="2026-10-01",
        description="creative cloud monthly subscription",
        amount_cents=-2499,
        category=cat.SOFTWARE,
        confidence=0.93,
        method="ml",
    )
    dumped = row.model_dump()
    assert dumped["method"] == "ml"
    assert dumped["confidence"] == pytest.approx(0.93)

    # Rules-only rows serialize with the new fields unset (API-compatible).
    rules_row = Transaction(
        id="txn-0002",
        date="2026-10-01",
        description="ADOBE",
        amount_cents=-2499,
        category=cat.SOFTWARE,
        reason="test",
    )
    assert rules_row.model_dump()["method"] is None
    assert rules_row.model_dump()["confidence"] is None
