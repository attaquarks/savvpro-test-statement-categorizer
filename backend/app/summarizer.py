"""Summary computation: totals by category with refund/transfer treatment.

The rules are sign- and category-based so user overrides integrate
naturally:

- Transfer rows are excluded from spending and income entirely and are
  reported separately (out/in).
- Refund rows are not new income. They offset the spending category they
  belong to (their refund_category). Refunds with no matched category
  are reported as "Refunds (unmatched)".
- Income rows add to income only.
- Needs Review rows are excluded from all money totals; their amount is
  reported as "held for review".
- A credit placed in a spending category (e.g. by a user override)
  offsets that category, like a refund.
"""

from collections import defaultdict

from . import categories as cat
from .models import CategoryTotal, Summary, Transaction

UNMATCHED_REFUNDS_LABEL = "Refunds (unmatched)"


def build_summary(transactions: list[Transaction]) -> Summary:
    spending: dict[str, int] = defaultdict(int)
    refunds_by_category: dict[str, int] = defaultdict(int)
    row_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)

    income_total = 0
    refunds_total = 0
    transfers_out = 0
    transfers_in = 0
    needs_review_count = 0
    needs_review_amount = 0

    for txn in transactions:
        amount = txn.amount_cents
        category_counts[txn.category] += 1

        if txn.category == cat.TRANSFER:
            if amount < 0:
                transfers_out += -amount
            else:
                transfers_in += amount

        elif txn.category == cat.REFUND:
            refunds_total += amount
            bucket = txn.refund_category
            if bucket and bucket in cat.SPENDING_SET:
                refunds_by_category[bucket] += amount
                row_counts[bucket] += 1
            else:
                refunds_by_category[UNMATCHED_REFUNDS_LABEL] += amount
                row_counts[UNMATCHED_REFUNDS_LABEL] += 1

        elif txn.category == cat.INCOME:
            income_total += amount

        elif txn.category == cat.NEEDS_REVIEW:
            needs_review_count += 1
            needs_review_amount += abs(amount)

        elif txn.category in cat.SPENDING_SET:
            if amount < 0:
                spending[txn.category] += -amount
                row_counts[txn.category] += 1
            elif amount > 0:
                # A credit placed in a spending category behaves like a
                # refund of that category.
                refunds_by_category[txn.category] += amount
                row_counts[txn.category] += 1

        else:
            # Unknown category string (e.g. from a stale client): keep it
            # out of every total and surface it for review instead.
            needs_review_count += 1
            needs_review_amount += abs(amount)

    total_spending = sum(spending.values())
    net_spending = total_spending - refunds_total

    rows = []
    for category in cat.SPENDING_CATEGORIES:
        spending_value = spending.get(category, 0)
        refund_value = refunds_by_category.get(category, 0)
        if spending_value or refund_value:
            rows.append(
                CategoryTotal(
                    category=category,
                    spending_cents=spending_value,
                    refunds_cents=refund_value,
                    net_cents=spending_value - refund_value,
                    transaction_count=row_counts.get(category, 0),
                )
            )
    unmatched = refunds_by_category.get(UNMATCHED_REFUNDS_LABEL, 0)
    if unmatched:
        rows.append(
            CategoryTotal(
                category=UNMATCHED_REFUNDS_LABEL,
                spending_cents=0,
                refunds_cents=unmatched,
                net_cents=-unmatched,
                transaction_count=row_counts.get(UNMATCHED_REFUNDS_LABEL, 0),
            )
        )

    rows.sort(key=lambda row: (-row.net_cents, row.category))

    return Summary(
        transaction_count=len(transactions),
        total_spending_cents=total_spending,
        total_refunds_cents=refunds_total,
        net_spending_cents=net_spending,
        total_income_cents=income_total,
        transfers_out_cents=transfers_out,
        transfers_in_cents=transfers_in,
        transfers_count=category_counts.get(cat.TRANSFER, 0),
        needs_review_count=needs_review_count,
        needs_review_amount_cents=needs_review_amount,
        by_category=rows,
    )
