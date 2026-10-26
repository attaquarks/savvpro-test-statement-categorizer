"""User-facing errors raised while parsing a statement.

Each error carries an HTTP status code so the API layer can translate it
into a clear response without knowing parser internals.
"""


class StatementParseError(Exception):
    """Base class for statement parsing failures."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UnsupportedFileError(StatementParseError):
    """The file type is not one we parse."""

    status_code = 415


class EmptyFileError(StatementParseError):
    """The upload contains no bytes."""

    status_code = 400


class FileTooLargeError(StatementParseError):
    """The upload exceeds the size limit."""

    status_code = 413


class StatementFormatError(StatementParseError):
    """The file is readable but does not match the documented format."""

    status_code = 400


class NoTransactionsError(StatementFormatError):
    """The file was readable but yielded zero usable transactions."""

    status_code = 422
