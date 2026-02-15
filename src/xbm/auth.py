"""Auth: OAuth 2.0 credential loading from environment."""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class OAuth2Credentials:
    client_id: str
    client_secret: str


def _check_file_permissions(env_file: Path) -> None:
    """Check that .env file has secure permissions (not world-readable)."""
    try:
        file_stat = env_file.stat()
        mode = file_stat.st_mode

        # Check if file is readable by others (world-readable)
        if mode & stat.S_IROTH:
            print(
                f"\u26a0\ufe0f  WARNING: {env_file} is world-readable!\n"
                f"   Run: chmod 600 {env_file}\n"
                f"   This protects your API credentials from other users.",
                file=sys.stderr
            )

        # Check if file is readable by group
        elif mode & stat.S_IRGRP:
            print(
                f"\u26a0\ufe0f  WARNING: {env_file} is group-readable!\n"
                f"   Run: chmod 600 {env_file}\n"
                f"   This protects your API credentials.",
                file=sys.stderr
            )
    except (OSError, AttributeError):
        # Ignore permission check errors on non-Unix systems
        pass


def load_credentials() -> OAuth2Credentials | None:
    """Load OAuth 2.0 client credentials from env vars. Returns None if not set."""
    # Try ~/.config/xbm/.env then cwd .env
    config_env = Path.home() / ".config" / "xbm" / ".env"
    if config_env.exists():
        _check_file_permissions(config_env)
        load_dotenv(config_env)

    # Check local .env file permissions if it exists
    local_env = Path.cwd() / ".env"
    if local_env.exists():
        _check_file_permissions(local_env)

    load_dotenv()  # cwd .env

    client_id = os.environ.get("X_CLIENT_ID")
    client_secret = os.environ.get("X_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    return OAuth2Credentials(client_id=client_id, client_secret=client_secret)
