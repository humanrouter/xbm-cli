"""Utility helpers for xbm-cli."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta


def parse_tweet_id(input_str: str) -> str:
    """Extract a tweet ID from a URL or raw numeric string."""
    # Limit input length to prevent ReDoS attacks
    if len(input_str) > 500:
        raise ValueError("Input too long for tweet ID/URL")

    # More specific regex to prevent ReDoS - match username more strictly
    match = re.search(r"(?:twitter\.com|x\.com)/([a-zA-Z0-9_]{1,15})/status/(\d{1,20})", input_str)
    if match:
        return match.group(2)

    stripped = input_str.strip()
    # Tweet IDs are numeric and typically 18-19 digits
    if re.fullmatch(r"\d{1,20}", stripped):
        return stripped
    raise ValueError(f"Invalid tweet ID or URL: {input_str[:100]}")


def parse_date_value(value: str) -> date:
    """Parse a date string into a date object using local timezone.

    Accepts 'today', 'yesterday', or 'YYYY-MM-DD'.
    """
    lower = value.strip().lower()
    today = datetime.now().date()
    if lower == "today":
        return today
    if lower == "yesterday":
        return today - timedelta(days=1)
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"Invalid date: {value!r}. Use 'today', 'yesterday', or YYYY-MM-DD."
        )


def resolve_date_range(
    since: str | None, until: str | None
) -> tuple[date, date] | None:
    """Resolve --since/--until strings into a (start_date, end_date) pair.

    Returns None if neither is specified. Raises ValueError if since > until.
    """
    if since is None and until is None:
        return None
    today = datetime.now().date()
    start = parse_date_value(since) if since else date.min
    end = parse_date_value(until) if until else today
    if start > end:
        raise ValueError(
            f"--since ({start}) is after --until ({end})"
        )
    return start, end
