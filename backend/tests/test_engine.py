"""Tests for the deterministic categorization engine."""

from app import categories as cat
from app.categorizer import classify


def _classify(desc, amount_cents):
    return classify(desc, amount_cents)


def test_known_merchants_map_to_their_categories():
    cases = [
        ("ADOBE CREATIVE CLOUD", -5499, cat.SOFTWARE),
        ("FIGMA.COM PRO", -1500, cat.SOFTWARE),
        ("UBER *TRIP HELP.UBER.COM", -2345, cat.TRAVEL),
        ("DELTA AIR LINES 006", -41260, cat.TRAVEL),
        ("STARBUCKS STORE 8842", -675, cat.MEALS),
        ("STAPLES CREDIT ACP", -6230, cat.OFFICE_SUPPLIES),
        ("BEST BUY #221", -129900, cat.HARDWARE),
        ("GOOGLE ADS", -15000, cat.ADVERTISING),
        ("LEGALZOOM", -9900, cat.PROFESSIONAL_SERVICES),
        ("COURSERA PLUS MONTHLY", -5900, cat.EDUCATION),
    ]
    for description, amount, expected in cases:
        result = _classify(description, amount)
        assert result.category == expected, description
        assert not result.needs_review
        assert result.rule_id and result.rule_id.startswith("M-")


def test_matching_is_case_and_punctuation_insensitive():
    assert _classify("adobe creative cloud", -5499).category == cat.SOFTWARE
    assert _classify("Apple.com/Bill", -999).category == cat.SOFTWARE
    assert _classify("Apple Store 123", -999).category == cat.HARDWARE


def test_unknown_merchant_goes_to_needs_review():
    result = _classify("JOES CAFE 9921", -1850)
    assert result.category == cat.NEEDS_REVIEW
    assert result.needs_review
    assert "No rule matched" in result.reason


def test_ambiguous_marketplace_is_never_autocategorized():
    result = _classify("AMAZON.COM AMZN MKTP", -8642)
    assert result.category == cat.NEEDS_REVIEW
    assert result.needs_review
    assert "marketplace" in result.reason


def test_specific_merchant_rule_beats_ambiguous_marketplace():
    result = _classify("AMAZON WEB SERVICES", -4900)
    assert result.category == cat.SOFTWARE


def test_transfers_in_both_directions_are_transfers():
    out = _classify("TRANSFER TO BUSINESS SAVINGS *8821", -200000)
    into = _classify("TRANSFER FROM BUSINESS SAVINGS *8821", 150000)
    assert out.category == cat.TRANSFER
    assert into.category == cat.TRANSFER
    assert not out.needs_review and not into.needs_review


def test_card_payment_is_a_transfer():
    assert _classify("CREDIT CARD PAYMENT", -120000).category == cat.TRANSFER


def test_fee_debit_is_fees_and_charges():
    result = _classify("MONTHLY SERVICE FEE", -1500)
    assert result.category == cat.FEES
    assert result.rule_id == "F-FEE"


def test_fee_beats_transfer_keyword():
    # "WIRE TRANSFER FEE" contains both FEE and TRANSFER; the fee wins.
    result = _classify("WIRE TRANSFER FEE", -2500)
    assert result.category == cat.FEES


def test_fee_credit_is_a_refund_of_fees():
    result = _classify("FEE REVERSAL", 1500)
    assert result.category == cat.REFUND
    assert result.refund_category == cat.FEES


def test_income_keywords_categorize_credits():
    for description in ["PAYROLL DEPOSIT", "INVOICE PAYMENT ACME CORP", "STRIPE PAYOUT", "INTEREST PAID"]:
        result = _classify(description, 10000)
        assert result.category == cat.INCOME, description


def test_income_keyword_on_a_debit_is_not_income():
    result = _classify("SALARY REVERSAL ADJUSTMENT", -500)
    assert result.category == cat.NEEDS_REVIEW


def test_credit_from_known_merchant_is_a_refund_not_income():
    result = _classify("REFUND ADOBE CREATIVE CLOUD", 5499)
    assert result.category == cat.REFUND
    assert result.refund_category == cat.SOFTWARE
    assert "not new income" in result.reason


def test_unmatched_refund_wording_goes_to_needs_review():
    result = _classify("REFUND ISSUED", 1000)
    assert result.category == cat.NEEDS_REVIEW
    assert result.needs_review


def test_unknown_credit_is_needs_review_not_income():
    result = _classify("MYSTERY CREDIT 4482", 25000)
    assert result.category == cat.NEEDS_REVIEW
    assert "could be income or a refund" in result.reason


def test_classify_is_deterministic():
    a = _classify("UBER *TRIP", -2345)
    b = _classify("UBER *TRIP", -2345)
    assert (a.category, a.reason, a.rule_id, a.refund_category, a.needs_review) == (
        b.category,
        b.reason,
        b.rule_id,
        b.refund_category,
        b.needs_review,
    )
