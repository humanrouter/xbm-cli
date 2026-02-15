"""Tests for xbm.utils."""

from datetime import date, timedelta

import pytest

from xbm.utils import parse_date_value, parse_tweet_id, resolve_date_range


class TestParseTweetId:
    def test_raw_numeric(self):
        assert parse_tweet_id("1234567890") == "1234567890"

    def test_raw_with_whitespace(self):
        assert parse_tweet_id("  1234567890  ") == "1234567890"

    def test_x_url(self):
        assert parse_tweet_id("https://x.com/user/status/1234567890") == "1234567890"

    def test_twitter_url(self):
        assert parse_tweet_id("https://twitter.com/elonmusk/status/9999") == "9999"

    def test_url_with_query_params(self):
        assert parse_tweet_id("https://x.com/user/status/123?s=20") == "123"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid tweet ID"):
            parse_tweet_id("not-a-tweet")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_tweet_id("")


class TestParseDateValue:
    def test_today(self):
        assert parse_date_value("today") == date.today()

    def test_yesterday(self):
        assert parse_date_value("yesterday") == date.today() - timedelta(days=1)

    def test_specific_date(self):
        assert parse_date_value("2026-02-14") == date(2026, 2, 14)

    def test_case_insensitive(self):
        assert parse_date_value("Today") == date.today()
        assert parse_date_value("YESTERDAY") == date.today() - timedelta(days=1)

    def test_whitespace(self):
        assert parse_date_value("  today  ") == date.today()

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            parse_date_value("not-a-date")

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            parse_date_value("02-14-2026")


class TestResolveDateRange:
    def test_neither_returns_none(self):
        assert resolve_date_range(None, None) is None

    def test_both_specified(self):
        result = resolve_date_range("2026-02-01", "2026-02-14")
        assert result == (date(2026, 2, 1), date(2026, 2, 14))

    def test_since_only(self):
        start, end = resolve_date_range("2026-02-01", None)
        assert start == date(2026, 2, 1)
        assert end == date.today()

    def test_until_only(self):
        start, end = resolve_date_range(None, "2026-02-14")
        assert start == date.min
        assert end == date(2026, 2, 14)

    def test_same_day(self):
        result = resolve_date_range("today", "today")
        today = date.today()
        assert result == (today, today)

    def test_since_after_until_raises(self):
        with pytest.raises(ValueError, match="--since .* is after --until"):
            resolve_date_range("2026-02-14", "2026-02-01")
