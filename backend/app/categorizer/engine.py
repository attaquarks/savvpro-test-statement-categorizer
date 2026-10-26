"""The categorization engine — plain, deterministic Python.

This module is "the brain" required by the task: no machine learning and
no external AI model, just ordered keyword rules whose decision can be
explained for every row.

Decision order (first match wins):

1. Fee keywords        -> Fees & Charges (a credit becomes a fee reversal,
                          i.e. a Refund offsetting Fees & Charges). Checked
                          before transfers so "WIRE TRANSFER FEE" is a fee.
2. Transfer keywords   -> Transfer (money between the user's own accounts,
                          never spending or income).
3. Income keywords     -> Income (credits only).
4. Merchant rules      -> spending category on a debit; on a credit the row
                          is a Refund offsetting that merchant's category,
                          not new income.
5. Ambiguous merchants -> Needs Review (never guess on marketplaces).
6. Refund wording      -> credit containing REFUND/REVERSAL without a
                          recognized merchant goes to Needs Review.
7. Fallback            -> Needs Review.
"""

from dataclasses import dataclass

from .. import categories as cat
from ..parsing.base import ParseOutcome, RawTransaction
from . import rules


@dataclass
class Classification:
    category: str
    needs_review: bool
    reason: str
    rule_id: str | None = None
    refund_category: str | None = None


def classify(description: str, amount_cents: int) -> Classification:
    """Classify one transaction from its description and signed amount."""
    tokens = rules.normalize(description)
    is_credit = amount_cents > 0
    is_debit = amount_cents < 0

    # 1. Fees. A debit is a fee expense; a credit is a fee reversal.
    fee = rules.find_rule(tokens, rules.FEE_RULES)
    if fee is not None:
        keywords = " ".join(fee.keywords)
        if is_debit:
            return Classification(
                cat.FEES,
                False,
                f"Fee keyword '{keywords}' — treated as a Fees & Charges expense.",
                fee.rule_id,
            )
        if is_credit:
            return Classification(
                cat.REFUND,
                False,
                f"Fee credit ('{keywords}') — treated as a reversal of Fees & Charges.",
                fee.rule_id,
                refund_category=cat.FEES,
            )

    # 2. Transfers between own accounts.
    transfer = rules.find_rule(tokens, rules.TRANSFER_RULES)
    if transfer is not None:
        keywords = " ".join(transfer.keywords)
        return Classification(
            cat.TRANSFER,
            False,
            f"Transfer keyword '{keywords}' — money moved between own accounts, "
            "not spending or income.",
            transfer.rule_id,
        )

    # 3. Income keywords (credits only; a debit with these words is not income).
    income = rules.find_rule(tokens, rules.INCOME_RULES)
    if income is not None and is_credit:
        keywords = " ".join(income.keywords)
        return Classification(
            cat.INCOME,
            False,
            f"Income keyword '{keywords}'.",
            income.rule_id,
        )

    # 4. Known merchants: debit = expense, credit = refund of that expense.
    merchant = rules.find_rule(tokens, rules.MERCHANT_RULES)
    if merchant is not None:
        if is_debit or amount_cents == 0:
            return Classification(
                merchant.category,
                False,
                f"Matched known merchant '{merchant.display}' -> {merchant.category}.",
                merchant.rule_id,
            )
        return Classification(
            cat.REFUND,
            False,
            f"Credit from known merchant '{merchant.display}' — treated as a refund "
            f"of {merchant.category}, not new income.",
            merchant.rule_id,
            refund_category=merchant.category,
        )

    # 5. Ambiguous marketplaces: never guess.
    ambiguous = rules.find_rule(tokens, rules.AMBIGUOUS_RULES)
    if ambiguous is not None:
        if is_debit or amount_cents == 0:
            return Classification(
                cat.NEEDS_REVIEW,
                True,
                f"'{ambiguous.display}' is a marketplace that could be supplies, "
                "equipment or personal spending — needs review.",
                ambiguous.rule_id,
            )
        return Classification(
            cat.NEEDS_REVIEW,
            True,
            f"Credit from ambiguous merchant '{ambiguous.display}' — could be a "
            "refund or income; needs review.",
            ambiguous.rule_id,
        )

    # 6. Explicit refund wording without a recognized merchant.
    refund = rules.find_rule(tokens, rules.REFUND_RULES)
    if refund is not None and is_credit:
        return Classification(
            cat.NEEDS_REVIEW,
            True,
            "Refund credit, but the original expense merchant is unrecognized — "
            "confirm what it offsets.",
            refund.rule_id,
        )

    # 7. Fallback: anything unrecognized goes to Needs Review.
    if is_credit:
        return Classification(
            cat.NEEDS_REVIEW,
            True,
            "Credit with no matching rule — could be income or a refund; needs review.",
        )
    return Classification(
        cat.NEEDS_REVIEW,
        True,
        "No rule matched — unrecognized merchant.",
    )


def categorize_statement(outcome: ParseOutcome) -> list:
    """Attach a classification to every parsed transaction, in order.

    Returns model.Transaction objects (imported locally to avoid a
    circular import at module load time).
    """
    from ..models import Transaction

    transactions = []
    for index, raw in enumerate(outcome.transactions, start=1):
        result = classify(raw.description, raw.amount_cents)
        transactions.append(
            Transaction(
                id=f"txn-{index:04d}",
                date=raw.date,
                description=raw.description,
                amount_cents=raw.amount_cents,
                category=result.category,
                needs_review=result.needs_review,
                reason=result.reason,
                rule_id=result.rule_id,
                refund_category=result.refund_category,
                source="engine",
            )
        )
    return transactions
