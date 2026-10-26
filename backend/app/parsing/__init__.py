"""Statement parsing entry point: dispatch a file to the right parser."""

import os

from .base import ParseOutcome
from .csv_parser import parse_csv
from .errors import UnsupportedFileError
from .pdf_parser import parse_pdf

SUPPORTED_EXTENSIONS = {".csv", ".pdf"}


def parse_statement(filename: str, data: bytes) -> ParseOutcome:
    """Parse an uploaded statement by file extension.

    Raises UnsupportedFileError for anything other than .csv/.pdf.
    """
    extension = os.path.splitext(filename or "")[1].lower()
    if extension == ".csv":
        return parse_csv(data)
    if extension == ".pdf":
        return parse_pdf(data)
    label = extension or "(no extension)"
    raise UnsupportedFileError(
        f"Unsupported file type {label!r}. Upload a .csv or .pdf statement "
        "in the documented format (see the README)."
    )
