"""Command line: `python -m watchdog collect|search|analyze|flags|review|stats`."""

from __future__ import annotations

import argparse
import os
import sys

from watchdog.detect import rules
from watchdog.sources.moltbook import DEFAULT_BASE_URL, MoltbookSource
from watchdog.store import FLAG_STATUSES, Store


def _store() -> Store:
    return Store(os.getenv("WATCHDOG_DB", "data/watchdog.db"))


def collect(args: argparse.Namespace) -> int:
    source = MoltbookSource(
        api_key=os.getenv("MOLTBOOK_API_KEY", ""),
        base_url=os.getenv("MOLTBOOK_BASE_URL", DEFAULT_BASE_URL),
    )
    store = _store()
    added = store.add_posts(source.fetch_recent(args.limit))
    print(f"Collected {added} new post(s); {store.count()} stored in total.")
    return 0


def search(args: argparse.Namespace) -> int:
    for row in _store().search(args.text, args.limit):
        snippet = row["body"].replace("\n", " ")[:160]
        print(f"[{row['source']}] {row['author'] or '?'} in {row['community'] or '?'}: {snippet}\n  {row['url']}")
    return 0


def stats(_: argparse.Namespace) -> int:
    print(f"{_store().count()} post(s) stored.")
    return 0


def analyze(args: argparse.Namespace) -> int:
    store = _store()
    rows = store.unanalyzed("rules", args.limit)
    added = sum(store.record_analysis(row["id"], "rules", rules.scan(store.post_from_row(row))) for row in rows)
    print(f"Rules checked {len(rows)} post(s) and raised {added} new flag(s).")
    if args.llm:
        from watchdog.detect.llm import ClaudeReviewer

        reviewer = ClaudeReviewer()
        flagged = store.flagged_posts_without("llm", args.llm_limit)
        for row in flagged:
            review = reviewer.review(store.post_from_row(row), store.flags_for(row["id"]))
            store.record_analysis(row["id"], "llm", review.flags)
            print(f"  post {row['id']}: {review.verdict} ({review.model})")
        print(f"Claude reviewed {len(flagged)} flagged post(s).")
    return 0


def flags(args: argparse.Namespace) -> int:
    rows = _store().list_flags(args.status, args.limit)
    for row in rows:
        print(f"#{row['id']} [{row['severity']}] {row['category']} via {row['analyzer']} ({row['rule_id']})\n"
              f"  {row['explanation']}\n  evidence: {row['evidence']}\n"
              f"  {row['author'] or '?'} in {row['community'] or '?'} · {row['url']}\n"
              f"  sha256 {row['content_sha256'][:16]}…")
    print(f"{len(rows)} {args.status} flag(s).")
    return 0


def review(args: argparse.Namespace) -> int:
    if not _store().set_flag_status(args.flag_id, args.decision):
        print(f"No flag #{args.flag_id}.", file=sys.stderr)
        return 1
    print(f"Flag #{args.flag_id} marked {args.decision}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="watchdog", description="Read-only AI agent watchdog.")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("collect", help="fetch recent public posts and store new ones")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(run=collect)

    p = commands.add_parser("search", help="search stored posts")
    p.add_argument("text")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(run=search)

    p = commands.add_parser("analyze", help="run the keyword rules (and optionally Claude) over stored posts")
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--llm", action="store_true", help="also ask Claude to review posts the rules flagged")
    p.add_argument("--llm-limit", type=int, default=20)
    p.set_defaults(run=analyze)

    p = commands.add_parser("flags", help="list flags for review, most severe first")
    p.add_argument("--status", choices=FLAG_STATUSES, default="open")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(run=flags)

    p = commands.add_parser("review", help="record your decision on a flag")
    p.add_argument("flag_id", type=int)
    p.add_argument("decision", choices=["confirmed", "dismissed", "open"])
    p.set_defaults(run=review)

    p = commands.add_parser("stats", help="show how many posts are stored")
    p.set_defaults(run=stats)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
