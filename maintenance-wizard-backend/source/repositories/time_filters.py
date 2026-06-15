"""Shared helpers for filtering the operational tables by time window.

The seed CSVs store their record time as TEXT in a mix of formats
(``DD-MM-YYYY HH:MM`` for anomaly/fault rows, ``YYYY-MM-DD HH:MM:SS`` for delay
logs, ``YYYY-MM-DD`` for daily sensor readings). Lexical string comparison is
only correct for the ISO ``YYYY-...`` variants, so windowing is done in Python
after parsing rather than in SQL, which keeps every table correct regardless of
its textual format.

All seed tables are timestamp-shifted at startup so the newest record lands at
"now"; callers therefore anchor windows on :func:`now` (naive local time, to
match the stored, timezone-naive values).
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Same formats the data loader recognises, tried in order.
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d-%m-%Y",
)


def parse_dt(value: object) -> datetime | None:
    """Parse a stored timestamp/date string against the known seed formats."""
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def now() -> datetime:
    """Anchor for relative windows (naive, matches the stored values)."""
    return datetime.now()


def cutoff(days: float) -> datetime:
    """The lower bound of a ``last <days> days`` window ending now."""
    return now() - timedelta(days=days)
