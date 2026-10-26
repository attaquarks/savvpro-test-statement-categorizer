"""FastAPI application for the statement categorizer.

Stateless by design: the client uploads a statement, receives the parsed
and categorized transactions plus a summary, and sends the (possibly
user-corrected) transaction list back to /api/summary to recompute
totals. Nothing is persisted.
"""

from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .categorizer import categorize_statement
from .models import SummaryRequest, SummaryResponse, UploadResponse
from .parsing import parse_statement
from .parsing.errors import (
    EmptyFileError,
    FileTooLargeError,
    StatementParseError,
)
from .summarizer import build_summary

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CSV_PATH = REPO_ROOT / "sample-statements" / "sample_statement.csv"
SAMPLE_PDF_PATH = REPO_ROOT / "sample-statements" / "sample_statement.pdf"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

app = FastAPI(
    title="Statement Categorizer API",
    version="1.0.0",
    description=(
        "Reads a bank/credit-card statement (CSV or text-based PDF), "
        "categorizes every transaction with deterministic rules, and "
        "returns a spending summary. The categorization brain is plain "
        "Python — no AI model."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StatementParseError)
async def statement_parse_error_handler(request, exc: StatementParseError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_statement(file: UploadFile = File(...)):
    """Parse and categorize an uploaded statement (CSV or text PDF)."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise EmptyFileError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise FileTooLargeError("File exceeds the 5 MB upload limit.")

    filename = file.filename or "statement"
    outcome = parse_statement(filename, data)
    transactions = categorize_statement(outcome)

    return UploadResponse(
        filename=filename,
        statement_type="pdf" if filename.lower().endswith(".pdf") else "csv",
        transaction_count=len(transactions),
        warnings=outcome.warnings,
        transactions=transactions,
        summary=build_summary(transactions),
    )


@app.post("/api/summary", response_model=SummaryResponse)
def recompute_summary(payload: SummaryRequest):
    """Recompute totals from the current transaction list.

    The client sends the full transaction list with any user category
    overrides applied; the summary is rebuilt from scratch so there is
    exactly one source of truth for the math.
    """
    return SummaryResponse(summary=build_summary(payload.transactions))


@app.get("/api/sample/csv")
def sample_csv():
    return FileResponse(
        SAMPLE_CSV_PATH,
        media_type="text/csv",
        filename="sample_statement.csv",
    )


@app.get("/api/sample/pdf")
def sample_pdf():
    return FileResponse(
        SAMPLE_PDF_PATH,
        media_type="application/pdf",
        filename="sample_statement.pdf",
    )


# Serve the built frontend when it exists, so `uvicorn app.main:app` alone
# can serve the whole product. In development the Vite dev server handles
# the UI and proxies /api here.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:

    @app.get("/")
    def root():
        return {
            "name": "Statement Categorizer API",
            "docs": "/docs",
            "note": "Build the frontend (npm run build in frontend/) to serve the UI from here.",
        }
