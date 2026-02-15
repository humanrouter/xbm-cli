"""X API v2 client — bookmark operations only (OAuth 2.0)."""

from __future__ import annotations

import re
from typing import Any

import httpx

from .auth import OAuth2Credentials
from .oauth2 import get_valid_access_token

API_BASE = "https://api.x.com/2"


def _merge_includes(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Merge includes from source into target, deduplicating by ID."""
    for key in ("users", "tweets", "media"):
        source_items = source.get(key, [])
        if not source_items:
            continue
        if key not in target:
            target[key] = []
        existing_ids = {item.get("id") or item.get("media_key") for item in target[key]}
        for item in source_items:
            item_id = item.get("id") or item.get("media_key")
            if item_id not in existing_ids:
                target[key].append(item)
                existing_ids.add(item_id)


class XApiClient:
    def __init__(self, oauth2_creds: OAuth2Credentials) -> None:
        self.oauth2_creds = oauth2_creds
        self._user_id: str | None = None
        self._http = httpx.Client(timeout=30.0)

    def __enter__(self) -> "XApiClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()

    def close(self) -> None:
        self._http.close()

    # ---- internal ----

    def _request(self, method: str, url: str, json_body: dict | None = None) -> dict[str, Any]:
        """Make an API request using OAuth 2.0 Bearer token."""
        access_token = get_valid_access_token(self.oauth2_creds.client_id, self.oauth2_creds.client_secret)
        headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        resp = self._http.request(method, url, headers=headers, json=json_body if json_body else None)
        return self._handle(resp)

    def _handle(self, resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code == 429:
            reset = resp.headers.get("x-rate-limit-reset", "unknown")
            raise RuntimeError(f"Rate limited. Resets at {reset}.")
        data = resp.json()
        if not resp.is_success:
            errors = data.get("errors", [])
            # Sanitize error messages to avoid exposing sensitive details
            if errors:
                msg = "; ".join(
                    self._sanitize_error_message(e.get("detail") or e.get("message", ""))
                    for e in errors
                )
            else:
                msg = "Request failed. Please check your credentials and try again."
            raise RuntimeError(f"API error (HTTP {resp.status_code}): {msg}")
        return data

    def _sanitize_error_message(self, msg: str) -> str:
        """Remove potentially sensitive information from error messages."""
        # Redact anything that looks like a token/key (long alphanumeric strings)
        sanitized = re.sub(r'\b[A-Za-z0-9]{32,}\b', '[REDACTED]', msg)
        # Limit message length to prevent information disclosure
        return sanitized[:200]

    def _get_user_id(self) -> str:
        """Get the authenticated user ID using the OAuth 2.0 token."""
        if self._user_id:
            return self._user_id
        data = self._request("GET", f"{API_BASE}/users/me")
        self._user_id = data["data"]["id"]
        return self._user_id

    # ---- bookmarks ----

    def get_bookmarks(
        self, max_results: int = 10, pagination_token: str | None = None
    ) -> dict[str, Any]:
        user_id = self._get_user_id()
        max_results = max(1, min(max_results, 100))
        params = {
            "max_results": str(max_results),
            "tweet.fields": "created_at,public_metrics,author_id,conversation_id,entities,lang,note_tweet,referenced_tweets",
            "expansions": "author_id,referenced_tweets.id,referenced_tweets.id.author_id,attachments.media_keys",
            "user.fields": "name,username,verified,profile_image_url",
            "media.fields": "url,preview_image_url,type",
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{API_BASE}/users/{user_id}/bookmarks?{qs}"
        return self._request("GET", url)

    def get_tweets_by_ids(self, tweet_ids: list[str]) -> dict[str, Any]:
        """Batch fetch tweets by IDs (up to 100). Uses OAuth 2.0 auth."""
        if not tweet_ids:
            return {"data": []}
        ids = ",".join(tweet_ids[:100])
        params = {
            "ids": ids,
            "tweet.fields": "created_at,public_metrics,author_id,conversation_id,entities,lang,note_tweet,referenced_tweets",
            "expansions": "author_id,referenced_tweets.id,referenced_tweets.id.author_id,attachments.media_keys",
            "user.fields": "name,username,verified,profile_image_url",
            "media.fields": "url,preview_image_url,type",
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{API_BASE}/tweets?{qs}"
        return self._request("GET", url)

    def bookmark_tweet(self, tweet_id: str) -> dict[str, Any]:
        user_id = self._get_user_id()
        return self._request("POST", f"{API_BASE}/users/{user_id}/bookmarks", {"tweet_id": tweet_id})

    def unbookmark_tweet(self, tweet_id: str) -> dict[str, Any]:
        user_id = self._get_user_id()
        return self._request("DELETE", f"{API_BASE}/users/{user_id}/bookmarks/{tweet_id}")
