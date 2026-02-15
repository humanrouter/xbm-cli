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

The `--since` and `--until` options filter by **when you bookmarked the tweet, not when the tweet was posted**. If you bookmark a tweet from last week today, `--since today` will include it because you added it today.

On first use, `xbm` syncs your bookmarks and records today's date for each one. After that, it detects new additions and tags them with the date you bookmarked them.

```bash
xbm list --since today               # Bookmarks I added today
xbm list --since 2026-02-01          # Everything I bookmarked since Feb 1
xbm -j list --since yesterday        # What I bookmarked yesterday, as JSON
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

### Turn xbm into a Claude Code Skill

You can make `xbm` a reusable [skill](https://code.claude.com/docs/en/skills) so it's always available as a slash command. Create the skill file:

```bash
mkdir -p ~/.claude/skills/xbm
cat > ~/.claude/skills/xbm/SKILL.md << 'SKILLEOF'
---
name: xbm
description: Manage X/Twitter bookmarks — list, add, remove, summarize, and organize.
user_invocable: true
---

You have access to the `xbm` CLI for managing X/Twitter bookmarks.

## Available commands

- `xbm list [--max N] [--since DATE] [--until DATE]` — List bookmarks
- `xbm add <tweet_id_or_url>` — Bookmark a tweet
- `xbm remove <tweet_id_or_url>` — Remove a bookmark
- `xbm auth status` — Check login status

## Output flags

- `-j` for JSON (best for processing), `-p` for TSV, `-md` for Markdown, `-v` for verbose

## Instructions

When the user asks about their bookmarks, use the xbm CLI to fetch, analyze,
or manage them. Default to `-j` (JSON) when you need to process the data, and
human-readable output when the user just wants to see results.

Always use `--max` to limit results when the user doesn't specify a count.
SKILLEOF
```

Now you can type `/xbm` in any Claude Code session to activate bookmark management.

## Automate with OpenClaw

[OpenClaw](https://github.com/clawdbot/clawdbot) (formerly Clawdbot) is an open-source AI assistant that runs Claude on your machine with built-in automation. Combined with `xbm`, it turns your bookmarks into an automated productivity system — syncing, summarizing, and acting on saved tweets on a schedule.

### Setup

Make sure `xbm` is installed and authenticated (`xbm auth status` should show "Logged in"), then add xbm instructions to your OpenClaw system prompt or session config so the agent knows the tool is available.

### Daily Bookmark Digest

Get a summary of what you bookmarked each day, delivered to your chat every morning:

```bash
openclaw cron add \
  --name "Bookmark digest" \
  --cron "0 8 * * *" \
  --tz "America/Chicago" \
  --session isolated \
  --message "Run xbm -j list --since yesterday. Summarize the bookmarks by topic, highlight the top 3 most interesting ones, and format as a morning briefing." \
  --announce
```

### Weekly Reading List

Compile a curated weekly reading list from your bookmarks every Sunday:

```bash
openclaw cron add \
  --name "Weekly reading list" \
  --cron "0 10 * * 0" \
  --tz "America/Chicago" \
  --session isolated \
  --message "Run xbm -j list --since 7-days-ago. Categorize all bookmarks into topics (AI, business, tech, etc.), rank by engagement metrics, and produce a markdown reading list with brief summaries for each."
```

### Bookmark Cleanup

Automatically review and prune stale bookmarks monthly:

```bash
openclaw cron add \
  --name "Bookmark cleanup" \
  --cron "0 9 1 * *" \
  --tz "America/Chicago" \
  --session isolated \
  --message "Run xbm -j list --max 100. Identify bookmarks that are likely outdated (broken links, deleted tweets, or topics no longer relevant). List them and remove each one with xbm remove <id>. Report what was cleaned up."
```

### Research Monitoring

Track bookmarks related to specific topics you're researching:

```bash
openclaw cron add \
  --name "AI research tracker" \
  --cron "0 18 * * *" \
  --tz "America/Chicago" \
  --session isolated \
  --message "Run xbm -j list --since today. Filter for bookmarks about AI, LLMs, or machine learning. If any are found, summarize the key findings and save to ~/notes/ai-research-log.md, appending today's date as a header."
```

### Save Bookmarks to Notion / Obsidian / Files

Export bookmarks on a schedule to your note-taking system:

```bash
openclaw cron add \
  --name "Export bookmarks" \
  --cron "0 22 * * *" \
  --tz "America/Chicago" \
  --session isolated \
  --message "Run xbm -md list --since today. Append the output to ~/notes/bookmarks/$(date +%Y-%m).md with today's date as a section header."
```

### One-Shot Reminders

Process bookmarks at a specific time — useful for "review this later" workflows:

```bash
# "Remind me to go through my bookmarks at 6pm"
openclaw cron add \
  --name "Bookmark review" \
  --at "18:00" \
  --session main \
  --system-event "Time to review bookmarks. Run xbm list --since today and present them for review." \
  --delete-after-run
```

### Why This Combo Works

| What | How |
|------|-----|
| `xbm` gives structured data | `-j` outputs clean JSON that the agent can parse and act on |
| OpenClaw runs autonomously | Cron jobs fire without you being at the terminal |
| Agent can take action | Not just reading — it can `xbm remove`, write files, send messages |
| Chat delivery | `--announce` sends results to WhatsApp, Telegram, Slack, etc. |
| Isolated sessions | Each cron job runs in its own session, no interference |

You're essentially turning your X bookmarks into an automated knowledge pipeline: bookmark interesting things throughout the day, and let OpenClaw + xbm handle the rest.

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
