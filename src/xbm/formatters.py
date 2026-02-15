"""Output formatters: human (rich), JSON, TSV/plain, markdown."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel


# ---- JSON ----

def output_json(data: Any, verbose: bool = False) -> None:
    """Raw JSON to stdout."""
    if not verbose and isinstance(data, dict):
        # Strip includes/meta, just emit data
        inner = data.get("data")
        if inner is not None:
            print(json.dumps(inner, indent=2, default=str))
            return
    print(json.dumps(data, indent=2, default=str))


# ---- Plain/TSV ----

def output_plain(data: Any, verbose: bool = False) -> None:
    """TSV output for piping."""
    if isinstance(data, dict):
        inner = data.get("data")
        if inner is None:
            inner = data
        if isinstance(inner, list):
            _plain_list(inner, verbose)
        elif isinstance(inner, dict):
            _plain_dict(inner, verbose)
        else:
            print(inner)
    elif isinstance(data, list):
        _plain_list(data, verbose)
    else:
        print(data)


def _plain_dict(d: dict, verbose: bool = False) -> None:
    skip = set() if verbose else {"public_metrics", "entities", "edit_history_tweet_ids", "attachments", "referenced_tweets", "profile_image_url"}
    for k, v in d.items():
        if not verbose and k in skip:
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, default=str)
        print(f"{k}\t{v}")


def _plain_list(items: list, verbose: bool = False) -> None:
    if not items:
        return
    if not isinstance(items[0], dict):
        for item in items:
            print(item)
        return
    # Pick columns based on verbose
    all_keys = list(items[0].keys())
    if verbose:
        keys = all_keys
    else:
        keys = [k for k in ["id", "author_id", "text", "created_at"] if k in all_keys]
        if not keys:
            keys = all_keys
    print("\t".join(keys))
    for item in items:
        vals = []
        for k in keys:
            v = item.get(k, "")
            if isinstance(v, (dict, list)):
                v = json.dumps(v, default=str)
            vals.append(str(v))
        print("\t".join(vals))


# ---- Markdown ----

def output_markdown(data: Any, title: str = "", verbose: bool = False) -> None:
    """Markdown output to stdout."""
    if isinstance(data, dict):
        inner = data.get("data")
        includes = data.get("includes", {})
        meta = data.get("meta", {})
        if inner is None:
            inner = data

        if isinstance(inner, list):
            _md_list(inner, includes, title, verbose)
        elif isinstance(inner, dict):
            _md_tweet(inner, includes, title, verbose)
        else:
            print(str(inner))

        if verbose and meta.get("next_token"):
            print(f"\n*Next page: `--next-token {meta['next_token']}`*")
    elif isinstance(data, list):
        _md_list(data, {}, title, verbose)
    else:
        print(str(data))


def _md_tweet(tweet: dict, includes: dict, title: str = "", verbose: bool = False) -> None:
    author = _resolve_author(tweet.get("author_id"), includes)
    tweet_id = tweet.get("id", "")
    text, previews = _expand_urls(tweet)

    if title:
        print(f"## {title}\n")

    print(f"**{author}**")
    if verbose:
        created = tweet.get("created_at", "")
        if created:
            print(f"*{created}*")
    print(f"\n{text}\n")

    # Show link previews
    for p in previews:
        if p.get("title"):
            print(f"> **{p['title']}**")
        if p.get("description"):
            print(f"> {p['description']}")
        if p.get("title") or p.get("description"):
            print()

    # Show referenced tweet (quote, retweet, reply)
    ref = _resolve_referenced_tweet(tweet, includes)
    if ref:
        ref_type, ref_tweet = ref
        ref_author = _resolve_author(ref_tweet.get("author_id"), includes)
        ref_text, _ = _expand_urls(ref_tweet)
        label = {"quoted": "Quote of", "retweeted": "Retweet of", "replied_to": "Reply to"}.get(ref_type, ref_type)
        print(f"> **{label} {ref_author}**: {ref_text}\n")

    if verbose:
        metrics = tweet.get("public_metrics", {})
        if metrics:
            parts = [f"{k.replace('_count', '')}: {v}" for k, v in metrics.items()]
            print(" | ".join(parts))
            print()
    print(f"ID: `{tweet_id}`")


def _md_list(items: list, includes: dict, title: str = "", verbose: bool = False) -> None:
    if not items:
        return
    if title:
        print(f"## {title}\n")
    for i, item in enumerate(items):
        if i > 0:
            print("\n---\n")
        _md_tweet(item, includes, verbose=verbose)


# ---- Rich (human-readable) ----

_console = Console(stderr=True)
_stdout = Console()


def output_human(data: Any, title: str = "", verbose: bool = False) -> None:
    """Pretty-print with rich."""
    if isinstance(data, dict):
        inner = data.get("data")
        includes = data.get("includes", {})
        meta = data.get("meta", {})
        if inner is None:
            inner = data

        if isinstance(inner, list):
            for item in inner:
                _human_tweet(item, includes, verbose=verbose)
        elif isinstance(inner, dict):
            _human_tweet(inner, includes, title, verbose)
        else:
            _stdout.print(inner)

        if verbose and meta.get("next_token"):
            _console.print(f"[dim]Next page: --next-token {meta['next_token']}[/dim]")
    elif isinstance(data, list):
        for item in data:
            _human_tweet(item, {}, verbose=verbose)
    else:
        _stdout.print(data)


def _resolve_author(author_id: str | None, includes: dict) -> str:
    if not author_id:
        return "?"
    users = includes.get("users", [])
    for u in users:
        if u.get("id") == author_id:
            return f"@{u.get('username', '?')}"
    return author_id


def _expand_urls(tweet: dict) -> tuple[str, list[dict]]:
    """Replace t.co links in text with expanded URLs; return (text, link_previews).

    Each link preview is a dict with keys: url, title, description (any may be absent).
    """
    text = tweet.get("text", "")
    note = tweet.get("note_tweet", {})
    if note and note.get("text"):
        text = note["text"]

    urls = tweet.get("entities", {}).get("urls", [])
    previews: list[dict] = []

    for u in urls:
        tco = u.get("url", "")
        expanded = u.get("unwound_url") or u.get("expanded_url") or ""

        # Replace t.co link with expanded URL in text
        if tco and expanded:
            text = text.replace(tco, expanded)

        # Collect link preview data
        title = u.get("title") or ""
        description = u.get("description") or ""
        if title or description:
            previews.append({"url": expanded, "title": title, "description": description})

    # X articles have title in a separate field
    article = tweet.get("article", {})
    if article and article.get("title"):
        previews.insert(0, {"url": "", "title": article["title"], "description": ""})

    return text, previews


def _resolve_referenced_tweet(tweet: dict, includes: dict) -> tuple[str, dict] | None:
    """Return (type, referenced_tweet_dict) or None."""
    refs = tweet.get("referenced_tweets")
    if not refs:
        return None
    ref = refs[0]  # primary reference
    ref_type = ref.get("type", "")  # "quoted", "retweeted", "replied_to"
    ref_id = ref.get("id")
    if not ref_id:
        return None
    for t in includes.get("tweets", []):
        if t.get("id") == ref_id:
            return ref_type, t
    return None


def _human_tweet(tweet: dict, includes: dict, title: str = "", verbose: bool = False) -> None:
    author = _resolve_author(tweet.get("author_id"), includes)
    tweet_id = tweet.get("id", "")
    text, previews = _expand_urls(tweet)

    content = f"[bold]{author}[/bold]"
    if verbose:
        created = tweet.get("created_at", "")
        content += f"  [dim]{created}[/dim]"
    content += f"\n\n{text}"

    # Show link previews
    for p in previews:
        if p.get("title"):
            content += f"\n\n[bold cyan]{p['title']}[/bold cyan]"
        if p.get("description"):
            content += f"\n[dim]{p['description']}[/dim]"

    # Show referenced tweet (quote, retweet, reply)
    ref = _resolve_referenced_tweet(tweet, includes)
    if ref:
        ref_type, ref_tweet = ref
        ref_author = _resolve_author(ref_tweet.get("author_id"), includes)
        ref_text, _ = _expand_urls(ref_tweet)
        label = {"quoted": "Quote of", "retweeted": "Retweet of", "replied_to": "Reply to"}.get(ref_type, ref_type)
        content += f"\n\n[dim]─── {label} {ref_author} ───[/dim]\n[dim]{ref_text}[/dim]"

    if verbose:
        metrics = tweet.get("public_metrics", {})
        if metrics:
            parts = [f"{k.replace('_count', '').replace('_', ' ')}: {v}" for k, v in metrics.items()]
            content += f"\n\n[dim]{' | '.join(parts)}[/dim]"

    panel_title = title or f"Tweet {tweet_id}"
    _stdout.print(Panel(content, title=panel_title, border_style="blue", expand=False))


# ---- Router ----

def format_output(data: Any, mode: str = "human", title: str = "", verbose: bool = False) -> None:
    """Route to the appropriate formatter."""
    if mode == "json":
        output_json(data, verbose)
    elif mode == "plain":
        output_plain(data, verbose)
    elif mode == "markdown":
        output_markdown(data, title, verbose)
    else:
        output_human(data, title, verbose)
