"""Category definitions shared by the categorizer and the summarizer.

Categories come in two groups:

- Spending categories: tax-relevant expense buckets for the target use case
  (a freelance designer sorting a business statement for tax time).
- Special buckets: Income, Refund, Transfer and Needs Review. These are not
  spending; the summarizer treats each one differently (see summarizer.py).
"""

SOFTWARE = "Software & Subscriptions"
TRAVEL = "Travel"
MEALS = "Meals & Entertainment"
OFFICE_SUPPLIES = "Office Supplies"
HARDWARE = "Hardware & Equipment"
ADVERTISING = "Advertising & Marketing"
PROFESSIONAL_SERVICES = "Professional Services"
EDUCATION = "Education & Training"
FEES = "Fees & Charges"

INCOME = "Income"
REFUND = "Refund"
TRANSFER = "Transfer"
NEEDS_REVIEW = "Needs Review"

SPENDING_CATEGORIES = [
    SOFTWARE,
    TRAVEL,
    MEALS,
    OFFICE_SUPPLIES,
    HARDWARE,
    ADVERTISING,
    PROFESSIONAL_SERVICES,
    EDUCATION,
    FEES,
]

INCOME_CATEGORIES = [INCOME]

SPECIAL_CATEGORIES = [REFUND, TRANSFER, NEEDS_REVIEW]

ALL_CATEGORIES = SPENDING_CATEGORIES + INCOME_CATEGORIES + SPECIAL_CATEGORIES

SPENDING_SET = set(SPENDING_CATEGORIES)
