"""Click CLI for xbm — X/Twitter bookmark manager."""

from __future__ import annotations

import click

from .api import XApiClient
from .auth import load_credentials
from .formatters import format_output
from .utils import parse_tweet_id, resolve_date_range


class State:
    def __init__(self, mode: str, verbose: bool = False) -> None:
        self.mode = mode
        self.verbose = verbose
        self._client: XApiClient | None = None

    @property
    def client(self) -> XApiClient:
        if self._client is None:
            oauth2_creds = load_credentials()
            if not oauth2_creds:
                raise click.ClickException(
                    "Missing X_CLIENT_ID and/or X_CLIENT_SECRET. "
                    "Add them to ~/.config/xbm/.env or set as environment variables."
                )
            self._client = XApiClient(oauth2_creds)
        return self._client

    def output(self, data, title: str = "") -> None:
        format_output(data, self.mode, title, verbose=self.verbose)


pass_state = click.make_pass_decorator(State)


@click.group()
@click.option("--json", "-j", "fmt", flag_value="json", help="JSON output")
@click.option("--plain", "-p", "fmt", flag_value="plain", help="TSV output for piping")
@click.option("--markdown", "-md", "fmt", flag_value="markdown", help="Markdown output")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose output (show metrics, timestamps, metadata)")
@click.pass_context
def cli(ctx, fmt, verbose):
    """xbm: CLI for managing X/Twitter bookmarks."""
    ctx.ensure_object(dict)
    ctx.obj = State(fmt or "human", verbose=verbose)


# ============================================================
# list / add / remove — flat bookmark commands
# ============================================================

@cli.command("list")
@click.option("--max", "max_results", default=10, type=int, help="Max results (1-100)")
@click.option("--since", default=None, help="Start date: 'today', 'yesterday', or YYYY-MM-DD")
@click.option("--until", "until_date", default=None, help="End date: 'today', 'yesterday', or YYYY-MM-DD")
@pass_state
def list_bookmarks(state, max_results, since, until_date):
    """List your bookmarks."""
    try:
        date_range = resolve_date_range(since, until_date)
    except ValueError as e:
        raise click.ClickException(str(e))

    if date_range is not None:
        from .bookmarks import fetch_date_filtered_bookmarks

        start_date, end_date = date_range
        data = fetch_date_filtered_bookmarks(state.client, start_date, end_date)
    else:
        data = state.client.get_bookmarks(max_results)
    state.output(data, "Bookmarks")


@cli.command("add")
@click.argument("id_or_url")
@pass_state
def add_bookmark(state, id_or_url):
    """Bookmark a tweet."""
    tid = parse_tweet_id(id_or_url)
    data = state.client.bookmark_tweet(tid)
    state.output(data, "Bookmarked")


@cli.command("remove")
@click.argument("id_or_url")
@pass_state
def remove_bookmark(state, id_or_url):
    """Remove a bookmark."""
    tid = parse_tweet_id(id_or_url)
    data = state.client.unbookmark_tweet(tid)
    state.output(data, "Unbookmarked")


# ============================================================
# auth
# ============================================================

@cli.group()
def auth():
    """OAuth 2.0 authentication."""


@auth.command("login")
@click.option("--port", default=8739, type=int, help="Callback port (default 8739)")
def auth_login(port):
    """Authorize with OAuth 2.0 (opens browser)."""
    from .oauth2 import authorize

    oauth2_creds = load_credentials()
    if not oauth2_creds:
        raise click.ClickException(
            "Missing X_CLIENT_ID and/or X_CLIENT_SECRET. "
            "Add them to ~/.config/xbm/.env or set as environment variables."
        )
    try:
        authorize(oauth2_creds.client_id, oauth2_creds.client_secret, port=port)
        click.echo("Logged in successfully.", err=True)
    except RuntimeError as e:
        raise click.ClickException(str(e))


@auth.command("status")
def auth_status():
    """Check OAuth 2.0 login status."""
    from .oauth2 import load_tokens

    tokens = load_tokens()
    if tokens is None:
        click.echo("Not logged in (no OAuth 2.0 tokens found).", err=True)
        raise SystemExit(1)

    if tokens.is_expired():
        click.echo("Logged in, but access token is expired. It will refresh automatically on next use.", err=True)
    else:
        click.echo("Logged in (OAuth 2.0 tokens valid).", err=True)

    click.echo(f"Scopes: {tokens.scope}", err=True)


@auth.command("logout")
def auth_logout():
    """Revoke OAuth 2.0 tokens and delete local token file."""
    from .oauth2 import delete_tokens, load_tokens, revoke_token

    tokens = load_tokens()
    if tokens is None:
        click.echo("Not logged in.", err=True)
        return

    oauth2_creds = load_credentials()
    if oauth2_creds:
        try:
            revoke_token(tokens.access_token, oauth2_creds.client_id, oauth2_creds.client_secret)
        except Exception:
            pass  # Best effort — still delete local tokens
        try:
            revoke_token(tokens.refresh_token, oauth2_creds.client_id, oauth2_creds.client_secret)
        except Exception:
            pass

    delete_tokens()
    click.echo("Logged out (tokens revoked and deleted).", err=True)


def main():
    cli()


if __name__ == "__main__":
    main()
