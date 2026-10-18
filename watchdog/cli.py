"""Command line: `python -m watchdog collect|search|stats`."""

from __future__ import annotations

import argparse
import os
import sys

from watchdog.sources.moltbook import DEFAULT_BASE_URL, MoltbookSource
from watchdog.store import Store


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

    p = commands.add_parser("stats", help="show how many posts are stored")
    p.set_defaults(run=stats)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
