"""Regenerate sample-statements/sample_statement.pdf from the sample CSV.

The PDF follows the documented text-based PDF statement format: one
transaction per line as `YYYY-MM-DD DESCRIPTION AMOUNT`. Run from the
backend directory after installing requirements-dev:

    python scripts/make_sample_pdf.py
"""

import csv
import sys
from pathlib import Path

from fpdf import FPDF

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CSV = REPO_ROOT / "sample-statements" / "sample_statement.csv"
OUTPUT_PDF = REPO_ROOT / "sample-statements" / "sample_statement.pdf"


def main() -> int:
    with open(SAMPLE_CSV, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = [
            (row["Date"], row["Description"], row["Amount"]) for row in reader
        ]

    pdf = FPDF(format="letter", unit="pt")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font("courier", "B", 12)
    pdf.cell(0, 20, text="WESTBANK BUSINESS CARD - FAKE SAMPLE STATEMENT", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("courier", "", 10)
    pdf.cell(0, 16, text="Account holder: Jamie Rivera (sample data, not a real person)", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 16, text="Period: 2026-03-02 to 2026-04-15", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    for date, description, amount in rows:
        line = f"{date}  {description:<38} {amount:>12}"
        pdf.cell(0, 14, text=line, new_x="LMARGIN", new_y="NEXT")

    OUTPUT_PDF.write_bytes(pdf.output())
    print(f"Wrote {OUTPUT_PDF} ({len(rows)} transactions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
