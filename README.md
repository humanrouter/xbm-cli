# xbm-cli

A focused CLI for managing your X/Twitter bookmarks from the terminal. No bloat — just bookmarks.

## Quick Start

```bash
# Install
pipx install git+https://github.com/thanhpham87/xbm-cli.git

# Set up credentials (one-time)
mkdir -p ~/.config/xbm
cat > ~/.config/xbm/.env << 'EOF'
X_CLIENT_ID=your_client_id_here
X_CLIENT_SECRET=your_client_secret_here
EOF
chmod 600 ~/.config/xbm/.env

# Log in
xbm auth login

# Use it
xbm list
```

## Install

Requires Python 3.11+.

```bash
# With pipx (recommended — installs globally, no venv needed)
pipx install git+https://github.com/thanhpham87/xbm-cli.git

# With uv
uv tool install git+https://github.com/thanhpham87/xbm-cli.git

# From source
git clone https://github.com/thanhpham87/xbm-cli.git
cd xbm-cli
pipx install .
```

## OAuth 2.0 Setup

You need a free X/Twitter developer account to get API credentials.

1. Go to the [X Developer Portal](https://developer.x.com/) and create an app (or use an existing one).

2. Under **App Settings → Keys and tokens**, find your **OAuth 2.0 Client ID and Client Secret**.

3. Under **App Settings → User authentication settings**, configure:
   - **Type of App**: Web App, Automated App or Bot (Confidential client)
   - **Callback URL**: `http://127.0.0.1:8739/callback`
   - **Website URL**: any valid URL (e.g. your GitHub profile)

4. Create your credentials file:

```bash
mkdir -p ~/.config/xbm
cat > ~/.config/xbm/.env << 'EOF'
X_CLIENT_ID=your_client_id_here
X_CLIENT_SECRET=your_client_secret_here
EOF
chmod 600 ~/.config/xbm/.env
```

5. Authorize (opens your browser):

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
xbm -j list                 # JSON (great for scripting)
xbm -p list                 # TSV (pipe to awk, cut, etc.)
xbm -md list                # Markdown
xbm -v list                 # Verbose (adds metrics, timestamps)
```

Combine flags:

```bash
xbm -j -v list --max 20    # Verbose JSON with full metadata
xbm -p list | cut -f3       # Extract just the tweet text
```

## Date-Filtered Bookmarks

The `--since` and `--until` options track when bookmarks were first seen locally. On first use, `xbm` syncs your bookmarks and records the date for each. Subsequent runs detect new additions.

```bash
xbm list --since today               # What did I bookmark today?
xbm list --since 2026-02-01          # Everything since Feb 1
xbm -j list --since yesterday        # Yesterday's bookmarks as JSON
```

State is stored in `~/.config/xbm/bookmark_state.json`.

## Using with Claude Code

`xbm` is designed to work great with [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Since it's a standard CLI with JSON output, Claude Code can use it as a tool to do productive things with your bookmarks:

**Summarize today's bookmarks:**
```
> Use xbm to get my bookmarks from today and summarize the key themes
```

**Research from saved threads:**
```
> Pull my recent bookmarks with xbm and identify any threads about AI research
```

**Organize bookmarks into categories:**
```
> Get my last 50 bookmarks with xbm -j list --max 50, then categorize them
> by topic and give me a markdown summary
```

**Clean up old bookmarks:**
```
> List my bookmarks from last month, show me the ones that look outdated,
> and remove them with xbm remove
```

**Export for notes:**
```
> Get all my bookmarks from this week with xbm -md list --since 2026-02-10
> and format them as a weekly reading digest
```

The JSON output mode (`-j`) is especially useful for Claude Code since it gives structured data that's easy to reason about and transform.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Missing X_CLIENT_ID" | Add credentials to `~/.config/xbm/.env` |
| "Not logged in" | Run `xbm auth login` |
| "Token refresh failed" | Refresh token expired — run `xbm auth login` again |
| Rate limited | Wait for the reset time shown in the error |
| Browser auth shows "Something went wrong" | Check your callback URL is exactly `http://127.0.0.1:8739/callback` in the Developer Portal, and that your app type is "Web App" |

## License

MIT
