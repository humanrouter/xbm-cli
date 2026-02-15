# xbm-cli

A focused CLI for managing your X/Twitter bookmarks.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- X/Twitter developer account with OAuth 2.0 credentials

## Install

```bash
# Install globally with uv
uv tool install .

# Or install in a virtual environment
uv sync
```

## OAuth 2.0 Setup

1. Go to the [X Developer Portal](https://developer.x.com/) and create an app (or use an existing one).

2. Under **App Settings → Keys and tokens**, find your **OAuth 2.0 Client ID and Client Secret**.

3. Under **App Settings → User authentication settings**, configure:
   - **Type**: Web App (Confidential client)
   - **Callback URL**: `http://127.0.0.1:8739/callback`

4. Create a `.env` file (either in `~/.config/xbm/.env` or in your working directory):

```bash
cp .env.example ~/.config/xbm/.env
chmod 600 ~/.config/xbm/.env
# Edit the file and fill in your credentials
```

5. Log in:

```bash
xbm auth login
```

## Usage

### List bookmarks

```bash
xbm list                    # Latest 10 bookmarks
xbm list --max 50           # Up to 50 bookmarks
xbm list --since today      # Bookmarks added today
xbm list --since yesterday --until today
xbm list --since 2026-01-01 --until 2026-01-31
```

### Add a bookmark

```bash
xbm add 1234567890
xbm add https://x.com/user/status/1234567890
```

### Remove a bookmark

```bash
xbm remove 1234567890
xbm remove https://x.com/user/status/1234567890
```

### Auth commands

```bash
xbm auth login     # Authorize via browser (OAuth 2.0 PKCE)
xbm auth status    # Check login status
xbm auth logout    # Revoke tokens and delete local credentials
```

## Output Formats

```bash
xbm list                    # Human-readable (Rich panels)
xbm -j list                 # JSON
xbm -p list                 # TSV (for piping)
xbm -md list                # Markdown
xbm -v list                 # Verbose (adds metrics, timestamps)
```

## Date-Filtered Bookmarks

The `--since` and `--until` options track when bookmarks were first seen locally. On first use, `xbm` syncs your bookmarks and records today's date for each. Subsequent runs detect new additions.

State is stored in `~/.config/xbm/bookmark_state.json`.

## Troubleshooting

- **"Missing X_CLIENT_ID"**: Set `X_CLIENT_ID` and `X_CLIENT_SECRET` in `~/.config/xbm/.env` or as environment variables.
- **"Not logged in"**: Run `xbm auth login` to authorize.
- **"Token refresh failed"**: Your refresh token may have expired. Run `xbm auth login` again.
- **Rate limited**: Wait for the reset time shown in the error message.
