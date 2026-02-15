"""OAuth 2.0 Authorization Code Flow with PKCE for X API."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import tempfile
import time
import webbrowser
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
REVOKE_URL = "https://api.x.com/2/oauth2/revoke"

DEFAULT_PORT = 8739
CALLBACK_TIMEOUT = 120  # seconds

SCOPES = "tweet.read users.read bookmark.read bookmark.write offline.access"

TOKEN_DIR = Path.home() / ".config" / "xbm"
TOKEN_FILE = TOKEN_DIR / "oauth2_tokens.json"


# ---- PKCE helpers ----

def generate_code_verifier() -> str:
    """Generate a random 128-character URL-safe code verifier."""
    return secrets.token_urlsafe(96)[:128]


def generate_code_challenge(verifier: str) -> str:
    """Generate a BASE64URL(SHA256(verifier)) code challenge."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---- Token storage ----

@dataclass
class OAuth2Tokens:
    access_token: str
    refresh_token: str
    expires_at: float  # unix timestamp
    scope: str

    def is_expired(self) -> bool:
        """Check if access token is expired (with 60-second buffer)."""
        return time.time() >= (self.expires_at - 60)


def save_tokens(tokens: OAuth2Tokens) -> None:
    """Save tokens to disk with secure permissions. Uses atomic write."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=TOKEN_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(asdict(tokens), f)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, TOKEN_FILE)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_tokens() -> OAuth2Tokens | None:
    """Load tokens from disk. Returns None if file doesn't exist or is invalid."""
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text())
        return OAuth2Tokens(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def delete_tokens() -> None:
    """Delete the token file from disk."""
    try:
        TOKEN_FILE.unlink(missing_ok=True)
    except OSError:
        pass


# ---- Local callback server ----

class _CallbackResult:
    """Mutable container for passing data out of the request handler."""
    code: str | None = None
    error: str | None = None
    state: str | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    result: _CallbackResult  # set by the server factory

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != "/callback":
            self._respond(400, "Invalid path. Expected /callback.")
            return

        params = parse_qs(parsed.query)

        if "error" in params:
            error_msg = params["error"][0]
            desc = params.get("error_description", [""])[0]
            self.result.error = f"{error_msg}: {desc}" if desc else error_msg
            self._respond(400, f"Authorization denied: {self.result.error}")
            return

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        if not code or not state:
            self.result.error = "Missing code or state parameter"
            self._respond(400, self.result.error)
            return

        self.result.code = code
        self.result.state = state
        self._respond(200, "Authorization successful! You can close this tab and return to the terminal.")

    def _respond(self, status: int, message: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = f"<html><body><h2>{message}</h2></body></html>"
        self.wfile.write(html.encode())

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stderr logging."""
        pass


def _run_callback_server(port: int, result: _CallbackResult, timeout: float) -> None:
    """Start a one-shot HTTP server that captures the OAuth callback."""
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = timeout
    # Attach the result container to the handler class
    _CallbackHandler.result = result
    server.handle_request()  # handle exactly one request
    server.server_close()


# ---- Token exchange ----

def _basic_auth_header(client_id: str, client_secret: str) -> str:
    """Build HTTP Basic auth header for confidential client."""
    pair = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(pair.encode()).decode()
    return f"Basic {encoded}"


def _exchange_code(
    code: str,
    verifier: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> OAuth2Tokens:
    """Exchange authorization code for tokens."""
    with httpx.Client(timeout=30.0) as http:
        resp = http.post(
            TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(client_id, client_secret),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
        )

    if not resp.is_success:
        detail = resp.text[:200]
        raise RuntimeError(f"Token exchange failed (HTTP {resp.status_code}): {detail}")

    data = resp.json()
    return OAuth2Tokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=time.time() + data["expires_in"],
        scope=data.get("scope", SCOPES),
    )


def refresh_tokens(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> OAuth2Tokens:
    """Exchange a refresh token for a new token pair."""
    with httpx.Client(timeout=30.0) as http:
        resp = http.post(
            TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(client_id, client_secret),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

    if not resp.is_success:
        detail = resp.text[:200]
        raise RuntimeError(
            f"Token refresh failed (HTTP {resp.status_code}): {detail}\n"
            "Your refresh token may have expired. Run: xbm auth login"
        )

    data = resp.json()
    return OAuth2Tokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=time.time() + data["expires_in"],
        scope=data.get("scope", SCOPES),
    )


# ---- Main flows ----

def authorize(client_id: str, client_secret: str, port: int = DEFAULT_PORT) -> OAuth2Tokens:
    """Run the full OAuth 2.0 PKCE authorization flow.

    Opens a browser for the user to authorize, waits for the callback,
    exchanges the code for tokens, and saves them to disk.
    """
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    state = secrets.token_urlsafe(32)

    auth_params = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"{AUTHORIZE_URL}?{auth_params}"

    # Start callback server in a thread
    result = _CallbackResult()
    server_thread = Thread(
        target=_run_callback_server,
        args=(port, result, CALLBACK_TIMEOUT),
        daemon=True,
    )
    server_thread.start()

    print(f"Opening browser for authorization...", file=sys.stderr)
    print(f"If the browser doesn't open, visit:\n{auth_url}", file=sys.stderr)
    webbrowser.open(auth_url)

    # Wait for callback
    server_thread.join(timeout=CALLBACK_TIMEOUT + 5)

    if result.error:
        raise RuntimeError(f"Authorization failed: {result.error}")

    if not result.code:
        raise RuntimeError("Authorization timed out. No callback received within 120 seconds.")

    # Validate state (CSRF protection)
    if result.state != state:
        raise RuntimeError("State mismatch — possible CSRF attack. Authorization aborted.")

    # Exchange code for tokens
    tokens = _exchange_code(code=result.code, verifier=verifier, redirect_uri=redirect_uri,
                            client_id=client_id, client_secret=client_secret)
    save_tokens(tokens)
    return tokens


def get_valid_access_token(client_id: str, client_secret: str) -> str:
    """Load tokens, refresh if expired, and return a valid access token."""
    tokens = load_tokens()
    if tokens is None:
        raise RuntimeError(
            "Not logged in with OAuth 2.0. Run: xbm auth login"
        )

    if tokens.is_expired():
        tokens = refresh_tokens(tokens.refresh_token, client_id, client_secret)
        save_tokens(tokens)

    return tokens.access_token


def revoke_token(token: str, client_id: str, client_secret: str) -> None:
    """Revoke a token at the X API revoke endpoint."""
    with httpx.Client(timeout=30.0) as http:
        http.post(
            REVOKE_URL,
            headers={
                "Authorization": _basic_auth_header(client_id, client_secret),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"token": token},
        )
