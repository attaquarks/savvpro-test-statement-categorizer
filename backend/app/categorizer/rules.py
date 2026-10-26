"""Rule tables for the categorization engine.

Every rule is a tuple of keyword tokens that must appear contiguously in
the normalized description (uppercase, punctuation collapsed to spaces).
Merchant rules carry the category they assign; "ambiguous" rules are
marketplaces whose purchases could belong to several categories — those
deliberately route to Needs Review instead of guessing.

Rule tables are checked in a fixed order by the engine (see engine.py):
fees, transfers, income keywords, merchant rules, ambiguous marketplaces,
refund wording, fallback.
"""

import re
from dataclasses import dataclass, field

from .. import categories as cat


def normalize(text: str) -> list[str]:
    """Uppercase a description and split it into alphanumeric tokens."""
    return [token for token in re.split(r"[^A-Z0-9]+", text.upper()) if token]


def contains_sequence(tokens: list[str], keyword: tuple[str, ...]) -> bool:
    """True when the keyword token tuple appears contiguously in tokens."""
    size = len(keyword)
    if size == 0 or size > len(tokens):
        return False
    return any(tokens[i : i + size] == list(keyword) for i in range(len(tokens) - size + 1))


@dataclass(frozen=True)
class KeywordRule:
    rule_id: str
    keywords: tuple[str, ...]
    category: str
    merchant: str = ""  # display name for merchant rules
    ambiguous: bool = False

    @property
    def display(self) -> str:
        return self.merchant or " ".join(self.keywords).title()


def _merchant(rule_id: str, category: str, display: str, *keywords: str) -> KeywordRule:
    return KeywordRule(rule_id, tuple(keywords), category, merchant=display)


def _type_rule(rule_id: str, category: str, *keywords: str) -> KeywordRule:
    return KeywordRule(rule_id, tuple(keywords), category)


# --- Transaction-type rules (checked before merchant rules) -----------------

FEE_RULES = [
    _type_rule("F-FEE", cat.FEES, "FEE"),
    _type_rule("F-SERVICE-CHARGE", cat.FEES, "SERVICE", "CHARGE"),
    _type_rule("F-MAINTENANCE", cat.FEES, "MAINTENANCE"),
    _type_rule("F-OVERDRAFT", cat.FEES, "OVERDRAFT"),
    _type_rule("F-FINANCE-CHARGE", cat.FEES, "FINANCE", "CHARGE"),
    _type_rule("F-INTEREST-CHARGE", cat.FEES, "INTEREST", "CHARGE"),
]

TRANSFER_RULES = [
    _type_rule("T-TRANSFER", cat.TRANSFER, "TRANSFER"),
    _type_rule("T-XFER", cat.TRANSFER, "XFER"),
    _type_rule("T-AUTOPAY", cat.TRANSFER, "AUTOPAY"),
    _type_rule("T-CREDIT-CARD", cat.TRANSFER, "CREDIT", "CARD"),
    _type_rule("T-WIRE-OUT", cat.TRANSFER, "WIRE", "OUT"),
    _type_rule("T-WIRE-TO", cat.TRANSFER, "WIRE", "TO"),
]

INCOME_RULES = [
    _type_rule("I-PAYROLL", cat.INCOME, "PAYROLL"),
    _type_rule("I-SALARY", cat.INCOME, "SALARY"),
    _type_rule("I-DIRECT-DEPOSIT", cat.INCOME, "DIRECT", "DEPOSIT"),
    _type_rule("I-DIRECT-DEP", cat.INCOME, "DIRECT", "DEP"),
    _type_rule("I-INVOICE-PAYMENT", cat.INCOME, "INVOICE", "PAYMENT"),
    _type_rule("I-CLIENT-PAYMENT", cat.INCOME, "CLIENT", "PAYMENT"),
    _type_rule("I-STRIPE-PAYOUT", cat.INCOME, "STRIPE", "PAYOUT"),
    _type_rule("I-INTEREST-PAID", cat.INCOME, "INTEREST", "PAID"),
    _type_rule("I-INTEREST-EARNED", cat.INCOME, "INTEREST", "EARNED"),
]

REFUND_RULES = [
    _type_rule("R-REFUND", cat.REFUND, "REFUND"),
    _type_rule("R-REVERSAL", cat.REFUND, "REVERSAL"),
    _type_rule("R-REVERSED", cat.REFUND, "REVERSED"),
]

# --- Merchant rules ----------------------------------------------------------
# Order matters only for readability; matching is exact per rule and the
# ambiguous table is checked separately after all merchants.

MERCHANT_RULES = [
    # Software & subscriptions
    _merchant("M-ADOBE", cat.SOFTWARE, "Adobe", "ADOBE"),
    _merchant("M-FIGMA", cat.SOFTWARE, "Figma", "FIGMA"),
    _merchant("M-GITHUB", cat.SOFTWARE, "GitHub", "GITHUB"),
    _merchant("M-DROPBOX", cat.SOFTWARE, "Dropbox", "DROPBOX"),
    _merchant("M-SLACK", cat.SOFTWARE, "Slack", "SLACK"),
    _merchant("M-NOTION", cat.SOFTWARE, "Notion", "NOTION"),
    _merchant("M-ZOOM", cat.SOFTWARE, "Zoom", "ZOOM"),
    _merchant("M-CANVA", cat.SOFTWARE, "Canva", "CANVA"),
    _merchant("M-GOOGLE-WORKSPACE", cat.SOFTWARE, "Google Workspace", "GOOGLE", "WORKSPACE"),
    _merchant("M-GOOGLE-CLOUD", cat.SOFTWARE, "Google Cloud", "GOOGLE", "CLOUD"),
    _merchant("M-GOOGLE-STORAGE", cat.SOFTWARE, "Google Storage", "GOOGLE", "STORAGE"),
    _merchant("M-MICROSOFT-365", cat.SOFTWARE, "Microsoft 365", "MICROSOFT", "365"),
    _merchant("M-OFFICE-365", cat.SOFTWARE, "Office 365", "OFFICE", "365"),
    _merchant("M-AWS", cat.SOFTWARE, "Amazon Web Services", "AMAZON", "WEB", "SERVICES"),
    _merchant("M-JETBRAINS", cat.SOFTWARE, "JetBrains", "JETBRAINS"),
    _merchant("M-APPLE-COM", cat.SOFTWARE, "Apple (apple.com)", "APPLE", "COM"),
    # Travel
    _merchant("M-UBER", cat.TRAVEL, "Uber", "UBER"),
    _merchant("M-LYFT", cat.TRAVEL, "Lyft", "LYFT"),
    _merchant("M-DELTA-AIR", cat.TRAVEL, "Delta Air Lines", "DELTA", "AIR"),
    _merchant("M-UNITED-AIR", cat.TRAVEL, "United Airlines", "UNITED", "AIRLINES"),
    _merchant("M-AMERICAN-AIR", cat.TRAVEL, "American Airlines", "AMERICAN", "AIRLINES"),
    _merchant("M-SOUTHWEST-AIR", cat.TRAVEL, "Southwest Airlines", "SOUTHWEST", "AIRLINES"),
    _merchant("M-AMTRAK", cat.TRAVEL, "Amtrak", "AMTRAK"),
    _merchant("M-MARRIOTT", cat.TRAVEL, "Marriott", "MARRIOTT"),
    _merchant("M-HILTON", cat.TRAVEL, "Hilton", "HILTON"),
    _merchant("M-AIRBNB", cat.TRAVEL, "Airbnb", "AIRBNB"),
    _merchant("M-SHELL", cat.TRAVEL, "Shell", "SHELL"),
    _merchant("M-CHEVRON", cat.TRAVEL, "Chevron", "CHEVRON"),
    # Meals & entertainment
    _merchant("M-STARBUCKS", cat.MEALS, "Starbucks", "STARBUCKS"),
    _merchant("M-BLUE-BOTTLE", cat.MEALS, "Blue Bottle", "BLUE", "BOTTLE"),
    _merchant("M-CHIPOTLE", cat.MEALS, "Chipotle", "CHIPOTLE"),
    _merchant("M-PANERA", cat.MEALS, "Panera", "PANERA"),
    _merchant("M-SWEETGREEN", cat.MEALS, "Sweetgreen", "SWEETGREEN"),
    _merchant("M-DOORDASH", cat.MEALS, "DoorDash", "DOORDASH"),
    _merchant("M-GRUBHUB", cat.MEALS, "Grubhub", "GRUBHUB"),
    _merchant("M-DOMINOS", cat.MEALS, "Domino's", "DOMINOS"),
    # Office supplies
    _merchant("M-STAPLES", cat.OFFICE_SUPPLIES, "Staples", "STAPLES"),
    _merchant("M-OFFICE-DEPOT", cat.OFFICE_SUPPLIES, "Office Depot", "OFFICE", "DEPOT"),
    _merchant("M-ULINE", cat.OFFICE_SUPPLIES, "Uline", "ULINE"),
    # Hardware & equipment
    _merchant("M-BEST-BUY", cat.HARDWARE, "Best Buy", "BEST", "BUY"),
    _merchant("M-BH-PHOTO", cat.HARDWARE, "B&H Photo", "B", "H", "PHOTO"),
    _merchant("M-NEWEGG", cat.HARDWARE, "Newegg", "NEWEGG"),
    _merchant("M-APPLE-STORE", cat.HARDWARE, "Apple Store", "APPLE", "STORE"),
    # Advertising & marketing
    _merchant("M-GOOGLE-ADS", cat.ADVERTISING, "Google Ads", "GOOGLE", "ADS"),
    _merchant("M-META-ADS", cat.ADVERTISING, "Meta Ads", "META", "ADS"),
    _merchant("M-FACEBOOK-ADS", cat.ADVERTISING, "Facebook Ads", "FACEBOOK", "ADS"),
    _merchant("M-MAILCHIMP", cat.ADVERTISING, "Mailchimp", "MAILCHIMP"),
    _merchant("M-SQUARESPACE", cat.ADVERTISING, "Squarespace", "SQUARESPACE"),
    _merchant("M-GODADDY", cat.ADVERTISING, "GoDaddy", "GODADDY"),
    # Professional services
    _merchant("M-LEGALZOOM", cat.PROFESSIONAL_SERVICES, "LegalZoom", "LEGALZOOM"),
    _merchant("M-QUICKBOOKS", cat.PROFESSIONAL_SERVICES, "QuickBooks", "QUICKBOOKS"),
    _merchant("M-UPWORK", cat.PROFESSIONAL_SERVICES, "Upwork", "UPWORK"),
    # Education & training
    _merchant("M-UDEMY", cat.EDUCATION, "Udemy", "UDEMY"),
    _merchant("M-COURSERA", cat.EDUCATION, "Coursera", "COURSERA"),
    _merchant("M-SKILLSHARE", cat.EDUCATION, "Skillshare", "SKILLSHARE"),
    _merchant("M-DOMESTIKA", cat.EDUCATION, "Domestika", "DOMESTIKA"),
]

# Marketplaces and payment platforms whose rows could belong to several
# categories. They are never auto-categorized; they go to Needs Review.
AMBIGUOUS_RULES = [
    KeywordRule("A-AMAZON", ("AMAZON",), cat.NEEDS_REVIEW, merchant="Amazon", ambiguous=True),
    KeywordRule("A-AMZN", ("AMZN",), cat.NEEDS_REVIEW, merchant="Amazon (AMZN)", ambiguous=True),
    KeywordRule("A-WALMART", ("WALMART",), cat.NEEDS_REVIEW, merchant="Walmart", ambiguous=True),
    KeywordRule("A-TARGET", ("TARGET",), cat.NEEDS_REVIEW, merchant="Target", ambiguous=True),
    KeywordRule("A-PAYPAL", ("PAYPAL",), cat.NEEDS_REVIEW, merchant="PayPal", ambiguous=True),
    KeywordRule("A-APPLE", ("APPLE",), cat.NEEDS_REVIEW, merchant="Apple", ambiguous=True),
]


def find_rule(tokens: list[str], rules: list[KeywordRule]) -> KeywordRule | None:
    """Return the first rule whose keyword sequence matches the tokens."""
    for rule in rules:
        if contains_sequence(tokens, rule.keywords):
            return rule
    return None
