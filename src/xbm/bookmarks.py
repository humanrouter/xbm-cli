"""Bookmark state management for date-filtered queries."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .api import XApiClient, _merge_includes

STATE_DIR = Path.home() / ".config" / "xbm"
STATE_FILE = STATE_DIR / "bookmark_state.json"

MAX_SYNC_PAGES = 15
BOOKMARKS_PER_PAGE = 100
PRUNE_DAYS = 90


def load_state() -> dict:
    """Load bookmark state from disk. Returns empty state if missing/invalid."""
    if not STATE_FILE.exists():
        return {"known_ids": {}}
    try:
        data = json.loads(STATE_FILE.read_text())
        if not isinstance(data.get("known_ids"), dict):
            return {"known_ids": {}}
        return data
    except (json.JSONDecodeError, OSError):
        return {"known_ids": {}}


def save_state(state: dict) -> None:
    """Save bookmark state to disk with secure permissions. Uses atomic write."""
    prune_state(state)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=STATE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, STATE_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def prune_state(state: dict, days: int = PRUNE_DAYS) -> None:
    """Remove entries older than `days` days to prevent unbounded growth."""
    cutoff = (datetime.now().date() - timedelta(days=days)).isoformat()
    known = state.get("known_ids", {})
    state["known_ids"] = {
        tid: d for tid, d in known.items() if d >= cutoff
    }


def sync_bookmarks(
    client: XApiClient, state: dict
) -> tuple[dict[str, dict], dict[str, Any]]:
    """Fetch bookmarks page by page, tagging new IDs with today's date.

    Stops when a full page consists entirely of known IDs, or after MAX_SYNC_PAGES.

    Returns:
        (tweets_by_id, merged_includes) — tweet data collected during sync.
    """
    today_str = datetime.now().date().isoformat()
    known_ids = state.setdefault("known_ids", {})
    tweets_by_id: dict[str, dict] = {}
    merged_includes: dict[str, Any] = {}
    pagination_token: str | None = None

    for _ in range(MAX_SYNC_PAGES):
        resp = client.get_bookmarks(
            max_results=BOOKMARKS_PER_PAGE, pagination_token=pagination_token
        )
        data = resp.get("data", [])
        if not data:
            break

        includes = resp.get("includes", {})
        _merge_includes(merged_includes, includes)

        all_known = True
        for tweet in data:
            tid = tweet["id"]
            tweets_by_id[tid] = tweet
            if tid not in known_ids:
                known_ids[tid] = today_str
                all_known = False

        if all_known:
            break

        next_token = resp.get("meta", {}).get("next_token")
        if not next_token:
            break
        pagination_token = next_token

    return tweets_by_id, merged_includes


def filter_by_date(state: dict, start_date: date, end_date: date) -> set[str]:
    """Return set of tweet IDs where first_seen is within [start_date, end_date]."""
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()
    return {
        tid
        for tid, d in state.get("known_ids", {}).items()
        if start_str <= d <= end_str
    }


def fetch_date_filtered_bookmarks(
    client: XApiClient,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """Full flow: sync, filter by date, fetch missing tweets, return response dict."""
    state = load_state()
    synced_tweets, synced_includes = sync_bookmarks(client, state)
    save_state(state)

    matching_ids = filter_by_date(state, start_date, end_date)
    if not matching_ids:
        return {"data": [], "includes": synced_includes}

    # Collect tweets: use synced data when available, batch-fetch the rest
    result_tweets: list[dict] = []
    missing_ids: list[str] = []

    for tid in matching_ids:
        if tid in synced_tweets:
            result_tweets.append(synced_tweets[tid])
        else:
            missing_ids.append(tid)

    result_includes = dict(synced_includes)

    # Batch fetch missing tweets (up to 100 per call)
    for i in range(0, len(missing_ids), 100):
        batch = missing_ids[i : i + 100]
        try:
            resp = client.get_tweets_by_ids(batch)
            for tweet in resp.get("data", []):
                result_tweets.append(tweet)
            if resp.get("includes"):
                _merge_includes(result_includes, resp["includes"])
        except RuntimeError:
            pass  # Deleted/suspended tweets — skip gracefully

    return {"data": result_tweets, "includes": result_includes}
