"""Shared types produced by the statement parsers."""

from dataclasses import dataclass, field


@dataclass
class RawTransaction:
    """One transaction extracted from a statement, before categorization."""

    date: str  # ISO YYYY-MM-DD
    description: str
    amount_cents: int  # signed: expenses negative, credits positive


@dataclass
class ParseOutcome:
    """Everything a parser extracted, including rows it had to skip."""

    transactions: list[RawTransaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
