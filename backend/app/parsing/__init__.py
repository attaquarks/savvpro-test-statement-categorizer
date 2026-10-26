"""Statement parsing entry point: dispatch a file to the right parser."""

import os

from .base import ParseOutcome
from .csv_parser import parse_csv
from .errors import StatementFormatError, UnsupportedFileError
from .pdf_parser import parse_pdf

SUPPORTED_EXTENSIONS = {".csv", ".pdf"}
CHARGE_SIGN_OPTIONS = {"negative", "positive"}


def normalize_charge_sign(charge_sign: str) -> str:
    if charge_sign not in CHARGE_SIGN_OPTIONS:
        raise StatementFormatError(
            "charge_sign must be 'negative' (expenses negative — the documented "
            "default) or 'positive' (charges listed positive, e.g. some American "
            "Express exports)."
        )
    return charge_sign


def parse_statement(filename: str, data: bytes, charge_sign: str = "negative") -> ParseOutcome:
    """Parse an uploaded statement by file extension.

    charge_sign is only meaningful for CSV files with a plain Amount
    column (see csv_parser). Raises UnsupportedFileError for anything
    other than .csv/.pdf and StatementFormatError for a bad charge_sign.
    """
    charge_sign = normalize_charge_sign(charge_sign)
    extension = os.path.splitext(filename or "")[1].lower()
    if extension == ".csv":
        return parse_csv(data, charge_sign=charge_sign)
    if extension == ".pdf":
        return parse_pdf(data)
    label = extension or "(no extension)"
    raise UnsupportedFileError(
        f"Unsupported file type {label!r}. Upload a .csv or .pdf statement "
        "in the documented format (see the README)."
    )
