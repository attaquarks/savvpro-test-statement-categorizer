"""Evaluation evidence for the ML tier.

Run from backend/:  ./.venv/Scripts/python.exe scripts/evaluate_ml.py

Part 1 scores the repo's custom sample statement (fake data authored
alongside the rules, so its intended category per row is known by hand)
and reports auto-categorized / sent-for-review / mismatches.

Part 2 runs whatever unlabeled sample CSVs exist in the reviewer's
Downloads folder (never committed) and reports only how many rows the
engine auto-categorized vs sent for review, and how many of the
auto-categorized rows came from the ML tier. No accuracy claim is made
for those files — they carry no ground truth.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.categorizer.engine import categorize_statement
from app.parsing import parse_csv
from app import categories as cat

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "sample-statements" / "sample_statement.csv"

# Author-intended labels for the fake sample statement (fake data, no real
# person or bank). Review-intended rows are marked Needs Review on purpose:
# marketplaces, a merchant no rule knows, and a plausible-but-unlabeled one.
INTENDED = {
    "ADOBE CREATIVE CLOUD": cat.SOFTWARE,
    "INVOICE PAYMENT ACME CORP": cat.INCOME,
    "UBER *TRIP HELP.UBER.COM": cat.TRAVEL,
    "STARBUCKS STORE 8842": cat.MEALS,
    "TRANSFER TO BUSINESS SAVINGS *8821": cat.TRANSFER,
    "STAPLES CREDIT ACP": cat.OFFICE_SUPPLIES,
    "GOOGLE ADS": cat.ADVERTISING,
    "AMAZON.COM AMZN MKTP": cat.NEEDS_REVIEW,
    "JOES CAFE 9921": cat.NEEDS_REVIEW,
    "MONTHLY SERVICE FEE": cat.FEES,
    "DELTA AIR LINES 006": cat.TRAVEL,
    "MARRIOTT BONVOY DOWNTOWN": cat.TRAVEL,
    "STRIPE PAYOUT": cat.INCOME,
    "BEST BUY #221": cat.HARDWARE,
    "FIGMA.COM": cat.SOFTWARE,
    "DOORDASH ORDER": cat.MEALS,
    "LEGALZOOM": cat.PROFESSIONAL_SERVICES,
    "COURSERA PLUS MONTHLY": cat.EDUCATION,
    "REFUND ADOBE CREATIVE CLOUD": cat.REFUND,
    "LYFT *RIDE": cat.TRAVEL,
    "PAYPAL *DESIGN ASSETS": cat.NEEDS_REVIEW,
    "NEWEGG.COM": cat.HARDWARE,
    "MAILCHIMP MONTHLY": cat.ADVERTISING,
    "INTEREST PAID": cat.INCOME,
    "TRANSFER FROM BUSINESS SAVINGS *8821": cat.TRANSFER,
    "SWEETGREEN": cat.MEALS,
    "REFUND DELTA AIR LINES 006": cat.REFUND,
    "ATM FEE WESTBANK ATM 4TH ST": cat.FEES,
    "UDEMY ONLINE COURSE": cat.EDUCATION,
    "QUICKBOOKS SELF EMPLOYED": cat.PROFESSIONAL_SERVICES,
    "FEE REVERSAL": cat.REFUND,
    "DOMESTIKA ILLUSTRATION COURSE": cat.EDUCATION,
    "HILTON GARDEN INN": cat.TRAVEL,
    "SUNNY DESIGN STUDIO CONTRACT": cat.NEEDS_REVIEW,
    "CREDIT CARD PAYMENT": cat.TRANSFER,
    "UPWORK MARKETPLACE FEE": cat.FEES  # fee wording wins by documented tier order
    ,
    "INTEREST CHARGE PURCHASES": cat.FEES,
}


def evaluate_sample() -> None:
    outcome = parse_csv(SAMPLE.read_bytes())
    rows = categorize_statement(outcome)
    auto = [r for r in rows if not r.needs_review]
    review = [r for r in rows if r.needs_review]
    by_ml = [r for r in auto if r.method == "ml"]

    correct_auto = [r for r in auto if INTENDED[r.description] == r.category]
    wrong_auto = [r for r in auto if INTENDED[r.description] != r.category
                  and INTENDED[r.description] != cat.NEEDS_REVIEW]
    expected_auto_but_review = [
        r for r in review
        if INTENDED[r.description] != cat.NEEDS_REVIEW and r.description in INTENDED
    ]
    correct_review = [r for r in review if INTENDED.get(r.description) == cat.NEEDS_REVIEW]

    print(f"sample statement: {len(rows)} rows")
    print(f"  auto-categorized: {len(auto)} (of which via ML tier: {len(by_ml)})")
    print(f"  sent for review:  {len(review)}")
    print(f"  auto rows matching intended label: {len(correct_auto)}")
    print(f"  auto rows NOT matching intended label: {len(wrong_auto)}")
    for r in wrong_auto:
        print(f"    - {r.description!r}: got {r.category}, intended {INTENDED[r.description]}")
    print(f"  review rows that were intended for auto (missed): {len(expected_auto_but_review)}")
    for r in expected_auto_but_review:
        print(f"    - {r.description!r} (intended {INTENDED[r.description]})")
    print(f"  review rows intended as review: {len(correct_review)}")


def evaluate_unlabeled(path: Path, label: str) -> None:
    if not path.exists():
        print(f"{label}: file not found, skipped")
        return
    try:
        outcome = parse_csv(path.read_bytes())
        rows = categorize_statement(outcome)
    except Exception as exc:  # noqa: BLE001 - evidence script, keep going
        print(f"{label}: parse failed: {exc}")
        return
    auto = [r for r in rows if not r.needs_review]
    by_ml = [r for r in auto if r.method == "ml"]
    review = [r for r in rows if r.needs_review]
    print(f"{label}: {len(rows)} rows parsed")
    print(f"  auto-categorized: {len(auto)} (of which via ML tier: {len(by_ml)})")
    print(f"  sent for review:  {len(review)}")
    print("  (unlabeled file — counts only, no accuracy claim)")


def main() -> None:
    evaluate_sample()
    downloads = Path.home() / "Downloads"
    evaluate_unlabeled(downloads / "bankstatements.csv", "Downloads/bankstatements.csv")
    evaluate_unlabeled(downloads / "1000-BT-Records" / "1000 BT Records.csv", "Downloads/1000 BT Records.csv")


if __name__ == "__main__":
    main()
