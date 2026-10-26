"""Pydantic models shared by the API and the categorizer."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

TransactionSource = Literal["engine", "user"]


class Transaction(BaseModel):
    """One statement transaction with its current classification.

    Amounts are integer cents (signed: expenses negative, credits
    positive) so totals never drift through float arithmetic.
    """

    id: str
    date: str  # ISO YYYY-MM-DD
    description: str
    amount_cents: int
    category: str
    needs_review: bool = False
    reason: str = ""
    rule_id: Optional[str] = None
    refund_category: Optional[str] = None
    source: TransactionSource = "engine"


class CategoryTotal(BaseModel):
    category: str
    spending_cents: int = 0
    refunds_cents: int = 0
    net_cents: int = 0
    transaction_count: int = 0


class Summary(BaseModel):
    """Aggregates computed from the current categories of all transactions.

    Spending totals are net of refunds: a refund offsets the spending
    category it belongs to. Transfers are excluded from every total.
    """

    currency: str = "USD"
    transaction_count: int = 0
    total_spending_cents: int = 0
    total_refunds_cents: int = 0
    net_spending_cents: int = 0
    total_income_cents: int = 0
    transfers_out_cents: int = 0
    transfers_in_cents: int = 0
    transfers_count: int = 0
    needs_review_count: int = 0
    needs_review_amount_cents: int = 0
    by_category: list[CategoryTotal] = Field(default_factory=list)


class UploadResponse(BaseModel):
    filename: str
    statement_type: str  # "csv" or "pdf"
    transaction_count: int
    warnings: list[str] = Field(default_factory=list)
    transactions: list[Transaction]
    summary: Summary


class SummaryRequest(BaseModel):
    """The current transaction list (with any user category overrides)."""

    transactions: list[Transaction]


class SummaryResponse(BaseModel):
    summary: Summary
