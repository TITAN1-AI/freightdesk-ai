"""Shared board-date parsing; explicit date prefixes, never timezone/locale inference."""

import re
from datetime import datetime


def local_date(raw, date_format="ISO"):
    if not raw:
        return None
    formats = [(r"^\d{4}-\d{2}-\d{2}(?=$|[ T])", "%Y-%m-%d")]
    if date_format == "US":
        formats.append((r"^\d{2}/\d{2}/\d{4}(?=$|\s)", "%m/%d/%Y"))
    for pattern, fmt in formats:
        match = re.match(pattern, raw)
        if match:
            try:
                return datetime.strptime(match[0], fmt).date()
            except ValueError:
                return None
    return None
