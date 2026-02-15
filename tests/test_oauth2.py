"""Tests for xbm.oauth2."""

import base64
import hashlib
import json
import time

import pytest

from xbm.oauth2 import (
    OAuth2Tokens,
    delete_tokens,
    generate_code_challenge,
    generate_code_verifier,
    load_tokens,
    save_tokens,
    TOKEN_FILE,
)


class TestPKCE:
    def test_verifier_length(self):
        verifier = generate_code_verifier()
        assert len(verifier) == 128

    def test_verifier_is_url_safe(self):
        verifier = generate_code_verifier()
        # URL-safe base64 characters only
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(c in allowed for c in verifier)

    def test_verifier_is_random(self):
        v1 = generate_code_verifier()
        v2 = generate_code_verifier()
        assert v1 != v2

    def test_challenge_is_s256(self):
        verifier = "test_verifier_string"
        challenge = generate_code_challenge(verifier)
        # Manually compute expected value
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert challenge == expected

    def test_challenge_no_padding(self):
        challenge = generate_code_challenge("abc")
        assert "=" not in challenge


class TestOAuth2Tokens:
    def test_not_expired(self):
        tokens = OAuth2Tokens(
            access_token="a",
            refresh_token="r",
            expires_at=time.time() + 3600,
            scope="tweet.read",
        )
        assert not tokens.is_expired()

    def test_expired(self):
        tokens = OAuth2Tokens(
            access_token="a",
            refresh_token="r",
            expires_at=time.time() - 10,
            scope="tweet.read",
        )
        assert tokens.is_expired()

    def test_expired_within_buffer(self):
        """Token expiring within the 60-second buffer should count as expired."""
        tokens = OAuth2Tokens(
            access_token="a",
            refresh_token="r",
            expires_at=time.time() + 30,  # 30s left, but buffer is 60s
            scope="tweet.read",
        )
        assert tokens.is_expired()


class TestTokenPersistence:
    @pytest.fixture(autouse=True)
    def _patch_token_file(self, tmp_path, monkeypatch):
        """Redirect token file to a temp directory."""
        token_file = tmp_path / "oauth2_tokens.json"
        monkeypatch.setattr("xbm.oauth2.TOKEN_FILE", token_file)
        monkeypatch.setattr("xbm.oauth2.TOKEN_DIR", tmp_path)
        self.token_file = token_file

    def test_save_and_load(self):
        tokens = OAuth2Tokens(
            access_token="acc",
            refresh_token="ref",
            expires_at=1700000000.0,
            scope="tweet.read users.read",
        )
        save_tokens(tokens)
        loaded = load_tokens()
        assert loaded is not None
        assert loaded.access_token == "acc"
        assert loaded.refresh_token == "ref"
        assert loaded.expires_at == 1700000000.0
        assert loaded.scope == "tweet.read users.read"

    def test_load_missing_file(self):
        assert load_tokens() is None

    def test_load_invalid_json(self):
        self.token_file.write_text("not json")
        assert load_tokens() is None

    def test_load_missing_fields(self):
        self.token_file.write_text(json.dumps({"access_token": "a"}))
        assert load_tokens() is None

    def test_delete_tokens(self):
        tokens = OAuth2Tokens(
            access_token="a", refresh_token="r", expires_at=0.0, scope="s"
        )
        save_tokens(tokens)
        assert self.token_file.exists()
        delete_tokens()
        assert not self.token_file.exists()

    def test_delete_tokens_no_file(self):
        """delete_tokens should not raise if file doesn't exist."""
        delete_tokens()

    def test_save_file_permissions(self):
        import stat
        tokens = OAuth2Tokens(
            access_token="a", refresh_token="r", expires_at=0.0, scope="s"
        )
        save_tokens(tokens)
        mode = self.token_file.stat().st_mode
        assert not (mode & stat.S_IROTH)
        assert not (mode & stat.S_IRGRP)

    def test_roundtrip_preserves_data(self):
        """Verify JSON roundtrip doesn't lose or alter data."""
        tokens = OAuth2Tokens(
            access_token="tok_" + "x" * 100,
            refresh_token="ref_" + "y" * 100,
            expires_at=1700000000.123,
            scope="tweet.read users.read bookmark.read bookmark.write offline.access",
        )
        save_tokens(tokens)
        loaded = load_tokens()
        assert loaded == tokens
