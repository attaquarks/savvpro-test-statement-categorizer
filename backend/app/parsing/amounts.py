"""Amount parsing for statement files.

The documented format uses signed amounts: expenses are negative and
credits are positive. Common bank-export quirks are tolerated:

- currency symbols and thousands separators:  $1,234.56
- parenthesised negatives:                    (54.99)
- trailing minus:                             54.99-
- CR/DR suffixes:                             54.99 CR / 54.99 DR

Amounts are returned as integer cents so totals never drift through
floating point arithmetic.
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_CR_DR_SUFFIX = re.compile(r"\s*(CR|DR)$", re.IGNORECASE)
_STRIP_CHARS = re.compile(r"[$\s,]")
_PLAIN_NUMBER = re.compile(r"\d+(\.\d+)?")


def parse_amount(raw) -> int:
    """Parse one amount token into signed cents.

    Raises ValueError when the value is missing or not recognizable.
    An explicit CR/DR suffix decides the sign; otherwise a leading or
    trailing minus (or parentheses) makes the amount negative.
    """
    if raw is None:
        raise ValueError("missing amount")

    text = str(raw).strip()
    if not text:
        raise ValueError("missing amount")

    cr_dr = None
    match = _CR_DR_SUFFIX.search(text)
    if match:
        cr_dr = match.group(1).upper()
        text = text[: match.start()].strip()

    negative = False
    text = _STRIP_CHARS.sub("", text)
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]

    if text.endswith("-"):
        negative = True
        text = text[:-1]
    if text.startswith("-"):
        negative = True
        text = text[1:]
    if text.endswith("+"):
        text = text[:-1]

    if not _PLAIN_NUMBER.fullmatch(text):
        raise ValueError(f"unrecognized amount {raw!r}")

    try:
        value = Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - guarded by regex
        raise ValueError(f"unrecognized amount {raw!r}") from exc

    cents = int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    if cr_dr == "DR":
        return -abs(cents)
    if cr_dr == "CR":
        return abs(cents)
    return -cents if negative else cents
