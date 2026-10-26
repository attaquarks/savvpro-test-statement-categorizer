"""Date parsing for statement files.

Supported formats (also documented in the README):

- 2026-03-14   ISO, the documented primary format
- 2026/03/14
- 03/14/2026   US month/day/year
- 03/14/26
- 14-Mar-2026
- 14 Mar 2026
- Mar 14, 2026

Ambiguous numeric dates such as 03/04/2026 are read as US month/day/year.
Anything else raises ValueError and the row is reported as a warning
rather than silently guessed.
"""

from datetime import datetime

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%b %d, %Y",
)


def parse_date(raw) -> str:
    """Parse one date token and return an ISO (YYYY-MM-DD) string."""
    if raw is None:
        raise ValueError("missing date")

    text = str(raw).strip()
    if not text:
        raise ValueError("missing date")

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    raise ValueError(f"unrecognized date {raw!r}")
