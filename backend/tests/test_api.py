"""API tests: upload, summary recompute, errors, sample endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CSV = REPO_ROOT / "sample-statements" / "sample_statement.csv"
SAMPLE_PDF = REPO_ROOT / "sample-statements" / "sample_statement.pdf"

SMALL_CSV = (
    "Date,Description,Amount\n"
    "2026-03-01,ADOBE CREATIVE CLOUD,-54.99\n"
    "2026-03-02,REFUND ADOBE CREATIVE CLOUD,54.99\n"
    "2026-03-03,JOES CAFE 9921,-18.50\n"
)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_small_csv_with_refund_and_unknown():
    response = client.post(
        "/api/upload",
        files={"file": ("statement.csv", SMALL_CSV.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["transaction_count"] == 3
    assert body["statement_type"] == "csv"

    by_id = {t["id"]: t for t in body["transactions"]}
    assert by_id["txn-0001"]["category"] == "Software & Subscriptions"
    assert by_id["txn-0002"]["category"] == "Refund"
    assert by_id["txn-0002"]["refund_category"] == "Software & Subscriptions"
    assert by_id["txn-0003"]["category"] == "Needs Review"
    assert by_id["txn-0003"]["needs_review"] is True

    summary = body["summary"]
    # The refund nets the Adobe expense to zero and is not income.
    assert summary["total_income_cents"] == 0
    assert summary["total_refunds_cents"] == 5499
    software = next(
        row for row in summary["by_category"] if row["category"] == "Software & Subscriptions"
    )
    assert software["net_cents"] == 0
    assert summary["needs_review_count"] == 1
    assert summary["needs_review_amount_cents"] == 1850


def test_upload_shipped_sample_csv_totals():
    response = client.post(
        "/api/upload",
        files={"file": ("sample_statement.csv", SAMPLE_CSV.read_bytes(), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    summary = body["summary"]

    assert body["transaction_count"] == 37
    assert summary["needs_review_count"] == 4
    assert summary["needs_review_amount_cents"] == 8642 + 1850 + 4500 + 25000
    assert summary["total_income_cents"] == 240000 + 118025 + 231
    assert summary["total_refunds_cents"] == 5499 + 41260 + 1500
    assert summary["transfers_out_cents"] == 200000 + 120000
    assert summary["transfers_in_cents"] == 150000
    assert summary["total_spending_cents"] == 301687
    assert summary["net_spending_cents"] == 301687 - 48259


def test_upload_pdf_statement():
    response = client.post(
        "/api/upload",
        files={"file": ("sample_statement.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["statement_type"] == "pdf"
    assert body["transaction_count"] == 37


def test_upload_empty_file_is_rejected():
    response = client.post(
        "/api/upload",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_unsupported_extension_is_rejected():
    response = client.post(
        "/api/upload",
        files={"file": ("transactions.xlsx", b"PK\x03\x04", "application/vnd.ms-excel")},
    )
    assert response.status_code == 415
    assert "csv" in response.json()["detail"]


def test_upload_oversized_file_is_rejected():
    big = b"Date,Description,Amount\n" + b"X" * (5 * 1024 * 1024)
    response = client.post(
        "/api/upload",
        files={"file": ("big.csv", big, "text/csv")},
    )
    assert response.status_code == 413


def test_upload_unrecognized_headers_returns_clear_error():
    response = client.post(
        "/api/upload",
        files={"file": ("weird.csv", b"Foo,Bar\n1,2\n", "text/csv")},
    )
    assert response.status_code == 400
    assert "header" in response.json()["detail"].lower()


def test_upload_all_positive_amounts_is_rejected():
    content = (
        "Date,Description,Amount\n"
        "2026-03-01,STAPLES,5.00\n"
        "2026-03-02,STARBUCKS,6.00\n"
    )
    response = client.post(
        "/api/upload",
        files={"file": ("unsigned.csv", content.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 400
    assert "signed" in response.json()["detail"]


def test_upload_malformed_rows_are_reported_as_warnings():
    content = (
        "Date,Description,Amount\n"
        "2026-03-01,GOOD MERCHANT,-5.00\n"
        "2026-03-02,BAD ROW,abc\n"
    )
    response = client.post(
        "/api/upload",
        files={"file": ("mixed.csv", content.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transaction_count"] == 1
    assert len(body["warnings"]) == 1
    assert "Row 3" in body["warnings"][0]


def test_summary_recompute_after_user_override():
    upload = client.post(
        "/api/upload",
        files={"file": ("sample_statement.csv", SAMPLE_CSV.read_bytes(), "text/csv")},
    )
    transactions = upload.json()["transactions"]

    # Fix the Amazon needs-review row by assigning it to Office Supplies.
    fixed = []
    for txn in transactions:
        if txn["description"].startswith("AMAZON.COM"):
            txn = {**txn, "category": "Office Supplies", "needs_review": False, "source": "user"}
        fixed.append(txn)

    response = client.post("/api/summary", json={"transactions": fixed})
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["needs_review_count"] == 3

    office = next(
        row for row in summary["by_category"] if row["category"] == "Office Supplies"
    )
    assert office["spending_cents"] == 6230 + 8642


def test_upload_type_column_bank_export_is_accepted():
    """Chase-style all-positive amounts + Type column (previously rejected)."""
    content = (
        "Date,Description,Type,Amount\n"
        "2026-03-02,ADOBE CREATIVE CLOUD,DEBIT,54.99\n"
        "2026-03-02,INVOICE PAYMENT ACME CORP,CREDIT,2400.00\n"
        "2026-03-03,TRANSFER TO SAVINGS,DEBIT,2000.00\n"
    )
    response = client.post(
        "/api/upload",
        files={"file": ("chase.csv", content.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    by_desc = {t["description"]: t for t in body["transactions"]}
    assert by_desc["ADOBE CREATIVE CLOUD"]["amount_cents"] == -5499
    assert by_desc["ADOBE CREATIVE CLOUD"]["category"] == "Software & Subscriptions"
    assert by_desc["TRANSFER TO SAVINGS"]["category"] == "Transfer"
    assert body["summary"]["total_income_cents"] == 240000


def test_upload_amex_style_needs_charge_sign_option():
    """Charges-positive exports (some Amex files) only work with the option."""
    content = (
        "Date,Description,Amount\n"
        "2026-03-02,ADOBE CREATIVE CLOUD,54.99\n"
        "2026-03-03,UBER *TRIP HELP.UBER.COM,23.45\n"
    )
    rejected = client.post(
        "/api/upload",
        files={"file": ("amex.csv", content.encode("utf-8"), "text/csv")},
    )
    assert rejected.status_code == 400
    assert "Charges are positive" in rejected.json()["detail"]

    accepted = client.post(
        "/api/upload",
        files={"file": ("amex.csv", content.encode("utf-8"), "text/csv")},
        data={"charge_sign": "positive"},
    )
    assert accepted.status_code == 200
    by_desc = {t["description"]: t for t in accepted.json()["transactions"]}
    assert by_desc["ADOBE CREATIVE CLOUD"]["amount_cents"] == -5499


def test_upload_rejects_invalid_charge_sign():
    response = client.post(
        "/api/upload",
        files={"file": ("ok.csv", SMALL_CSV.encode("utf-8"), "text/csv")},
        data={"charge_sign": "sideways"},
    )
    assert response.status_code == 400
    assert "charge_sign" in response.json()["detail"]


def test_sample_csv_endpoint_serves_the_file():
    response = client.get("/api/sample/csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("Date,")


def test_sample_pdf_endpoint_serves_the_file():
    response = client.get("/api/sample/pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
