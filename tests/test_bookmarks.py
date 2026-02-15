"""Tests for xbm.bookmarks."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from xbm.api import _merge_includes
from xbm.bookmarks import (
    STATE_FILE,
    fetch_date_filtered_bookmarks,
    filter_by_date,
    load_state,
    prune_state,
    save_state,
    sync_bookmarks,
)


class TestLoadSaveState:
    def test_load_missing_file(self, tmp_path):
        with patch("xbm.bookmarks.STATE_FILE", tmp_path / "missing.json"):
            state = load_state()
        assert state == {"known_ids": {}}

    def test_load_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        with patch("xbm.bookmarks.STATE_FILE", f):
            state = load_state()
        assert state == {"known_ids": {}}

    def test_load_missing_known_ids(self, tmp_path):
        f = tmp_path / "state.json"
        f.write_text('{"other": "data"}')
        with patch("xbm.bookmarks.STATE_FILE", f):
            state = load_state()
        assert state == {"known_ids": {}}

    def test_save_and_load_roundtrip(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = {"known_ids": {"123": "2026-02-14", "456": "2026-02-13"}}
        with (
            patch("xbm.bookmarks.STATE_FILE", state_file),
            patch("xbm.bookmarks.STATE_DIR", tmp_path),
        ):
            save_state(state)
            assert state_file.exists()
            assert oct(state_file.stat().st_mode & 0o777) == "0o600"
            loaded = load_state()
        assert loaded["known_ids"]["123"] == "2026-02-14"
        assert loaded["known_ids"]["456"] == "2026-02-13"


class TestPruneState:
    def test_prune_old_entries(self):
        old_date = (date.today() - timedelta(days=91)).isoformat()
        recent_date = date.today().isoformat()
        state = {"known_ids": {"old": old_date, "recent": recent_date}}
        prune_state(state)
        assert "old" not in state["known_ids"]
        assert "recent" in state["known_ids"]

    def test_prune_keeps_boundary(self):
        boundary_date = (date.today() - timedelta(days=90)).isoformat()
        state = {"known_ids": {"boundary": boundary_date}}
        prune_state(state)
        assert "boundary" in state["known_ids"]


class TestMergeIncludes:
    def test_merge_users(self):
        target = {"users": [{"id": "1", "name": "Alice"}]}
        source = {"users": [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]}
        _merge_includes(target, source)
        assert len(target["users"]) == 2

    def test_merge_empty_target(self):
        target = {}
        source = {"users": [{"id": "1"}], "tweets": [{"id": "t1"}]}
        _merge_includes(target, source)
        assert len(target["users"]) == 1
        assert len(target["tweets"]) == 1

    def test_merge_media_by_media_key(self):
        target = {"media": [{"media_key": "m1", "type": "photo"}]}
        source = {"media": [{"media_key": "m1"}, {"media_key": "m2", "type": "video"}]}
        _merge_includes(target, source)
        assert len(target["media"]) == 2

    def test_merge_empty_source(self):
        target = {"users": [{"id": "1"}]}
        source = {}
        _merge_includes(target, source)
        assert len(target["users"]) == 1


class TestSyncBookmarks:
    def _make_client(self, pages):
        """Create a mock client that returns the given pages of bookmark data."""
        client = MagicMock()
        responses = []
        for tweets, next_token in pages:
            resp = {
                "data": [{"id": t} for t in tweets],
                "includes": {"users": [{"id": f"u{t}"} for t in tweets]},
                "meta": {},
            }
            if next_token:
                resp["meta"]["next_token"] = next_token
            responses.append(resp)
        client.get_bookmarks.side_effect = responses
        return client

    def test_new_bookmarks_detected(self):
        client = self._make_client([
            (["1", "2", "3"], None),
        ])
        state = {"known_ids": {}}
        tweets_by_id, includes = sync_bookmarks(client, state)
        assert set(state["known_ids"].keys()) == {"1", "2", "3"}
        assert all(d == date.today().isoformat() for d in state["known_ids"].values())
        assert set(tweets_by_id.keys()) == {"1", "2", "3"}

    def test_stops_at_known_ids(self):
        client = self._make_client([
            (["1", "2"], "token2"),
            (["3", "4"], None),  # all known
        ])
        state = {"known_ids": {"3": "2026-02-10", "4": "2026-02-10"}}
        sync_bookmarks(client, state)
        # Should have called get_bookmarks twice
        assert client.get_bookmarks.call_count == 2
        # New IDs added, old ones keep original date
        assert state["known_ids"]["1"] == date.today().isoformat()
        assert state["known_ids"]["3"] == "2026-02-10"

    def test_paginates_when_new_ids_found(self):
        client = self._make_client([
            (["1", "2"], "token2"),
            (["3", "4"], "token3"),
            (["5", "6"], None),  # all known
        ])
        state = {"known_ids": {"5": "2026-02-01", "6": "2026-02-01"}}
        sync_bookmarks(client, state)
        assert client.get_bookmarks.call_count == 3

    def test_empty_response(self):
        client = MagicMock()
        client.get_bookmarks.return_value = {"data": [], "meta": {}}
        state = {"known_ids": {}}
        tweets_by_id, includes = sync_bookmarks(client, state)
        assert tweets_by_id == {}
        assert state["known_ids"] == {}


class TestFilterByDate:
    def test_filter_range(self):
        state = {
            "known_ids": {
                "1": "2026-02-10",
                "2": "2026-02-12",
                "3": "2026-02-14",
                "4": "2026-02-15",
            }
        }
        result = filter_by_date(state, date(2026, 2, 12), date(2026, 2, 14))
        assert result == {"2", "3"}

    def test_filter_single_day(self):
        state = {"known_ids": {"1": "2026-02-14", "2": "2026-02-13"}}
        result = filter_by_date(state, date(2026, 2, 14), date(2026, 2, 14))
        assert result == {"1"}

    def test_filter_empty_state(self):
        result = filter_by_date({"known_ids": {}}, date(2026, 2, 1), date(2026, 2, 28))
        assert result == set()

    def test_filter_no_matches(self):
        state = {"known_ids": {"1": "2026-01-01"}}
        result = filter_by_date(state, date(2026, 2, 1), date(2026, 2, 28))
        assert result == set()


class TestFetchDateFilteredBookmarks:
    def test_returns_synced_tweets(self, tmp_path):
        client = MagicMock()
        today = date.today().isoformat()

        client.get_bookmarks.return_value = {
            "data": [
                {"id": "1", "text": "hello"},
                {"id": "2", "text": "world"},
            ],
            "includes": {"users": [{"id": "u1"}, {"id": "u2"}]},
            "meta": {},
        }

        state_file = tmp_path / "state.json"
        with (
            patch("xbm.bookmarks.STATE_FILE", state_file),
            patch("xbm.bookmarks.STATE_DIR", tmp_path),
        ):
            result = fetch_date_filtered_bookmarks(
                client, date.today(), date.today()
            )

        assert len(result["data"]) == 2
        assert any(t["id"] == "1" for t in result["data"])

    def test_batch_fetches_missing_tweets(self, tmp_path):
        client = MagicMock()
        today = date.today().isoformat()

        # Sync returns empty (no new bookmarks)
        client.get_bookmarks.return_value = {"data": [], "meta": {}}

        # Batch fetch returns the tweets
        client.get_tweets_by_ids.return_value = {
            "data": [{"id": "old1", "text": "old tweet"}],
            "includes": {"users": [{"id": "u_old"}]},
        }

        # Pre-populate state with a tweet from today
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"known_ids": {"old1": today}}))
        os.chmod(state_file, 0o600)

        with (
            patch("xbm.bookmarks.STATE_FILE", state_file),
            patch("xbm.bookmarks.STATE_DIR", tmp_path),
        ):
            result = fetch_date_filtered_bookmarks(
                client, date.today(), date.today()
            )

        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == "old1"
        client.get_tweets_by_ids.assert_called_once_with(["old1"])

    def test_no_matches_returns_empty(self, tmp_path):
        client = MagicMock()
        client.get_bookmarks.return_value = {"data": [], "meta": {}}

        state_file = tmp_path / "state.json"
        with (
            patch("xbm.bookmarks.STATE_FILE", state_file),
            patch("xbm.bookmarks.STATE_DIR", tmp_path),
        ):
            result = fetch_date_filtered_bookmarks(
                client, date(2026, 1, 1), date(2026, 1, 1)
            )

        assert result["data"] == []

    def test_handles_batch_fetch_error_gracefully(self, tmp_path):
        client = MagicMock()
        today = date.today().isoformat()

        client.get_bookmarks.return_value = {"data": [], "meta": {}}
        client.get_tweets_by_ids.side_effect = RuntimeError("API error")

        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"known_ids": {"del1": today}}))
        os.chmod(state_file, 0o600)

        with (
            patch("xbm.bookmarks.STATE_FILE", state_file),
            patch("xbm.bookmarks.STATE_DIR", tmp_path),
        ):
            result = fetch_date_filtered_bookmarks(
                client, date.today(), date.today()
            )

        # Should not raise, just return empty data
        assert result["data"] == []
