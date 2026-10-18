"""Command line: `python -m watchdog collect|search|analyze|flags|review|report|audit|stats`."""

from __future__ import annotations

import argparse
import os
import sys

from watchdog import report as reports
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
        print(f"#{row['id']} on post #{row['post_id']} [{row['severity']}] {row['category']} via {row['analyzer']} ({row['rule_id']})\n"
              f"  {row['explanation']}\n  evidence: {row['evidence']}\n"
              f"  {row['author'] or '?'} in {row['community'] or '?'} · {row['url']}\n"
              f"  sha256 {row['content_sha256'][:16]}…")
    print(f"{len(rows)} {args.status} flag(s).")
    return 0


def _reviewer(args: argparse.Namespace) -> str:
    return args.reviewer or os.getenv("WATCHDOG_REVIEWER", "")


def review(args: argparse.Namespace) -> int:
    if not _store().set_flag_status(args.flag_id, args.decision, _reviewer(args), args.note):
        print(f"No flag #{args.flag_id}.", file=sys.stderr)
        return 1
    print(f"Flag #{args.flag_id} marked {args.decision}.")
    return 0


def report(args: argparse.Namespace) -> int:
    store = _store()
    post = store.get_post(args.post_id)
    if post is None:
        print(f"No post #{args.post_id}.", file=sys.stderr)
        return 1
    confirmed = store.flag_rows(args.post_id, "confirmed")
    keys = args.channel or reports.suggested_channels([f["category"] for f in confirmed])
    for key in keys:
        text = reports.draft(post, confirmed, key)
        path = reports.write_draft(args.out, args.post_id, key, text)
        store.log(_reviewer(args), "draft_report", f"{key}: {path}", post_id=args.post_id)
        print(f"Drafted {path}")
    print("Nothing was sent. Review each draft and send it yourself.")
    return 0


def audit(args: argparse.Namespace) -> int:
    for row in _store().audit(args.limit):
        target = f"flag #{row['flag_id']}" if row["flag_id"] else f"post #{row['post_id']}"
        print(f"{row['at']} {row['actor']} {row['action']} {target}: {row['detail']}")
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
    p.add_argument("--note", default="", help="why you decided this (kept in the audit log)")
    p.add_argument("--reviewer", default="", help="your name for the audit log (or set WATCHDOG_REVIEWER)")
    p.set_defaults(run=review)

    p = commands.add_parser("report", help="draft reports from a post's confirmed flags (never sends)")
    p.add_argument("post_id", type=int)
    p.add_argument("--channel", action="append", choices=sorted(reports.CHANNELS),
                   help="channel to draft for; repeatable. Default: the suggested channels")
    p.add_argument("--out", default=os.getenv("WATCHDOG_REPORTS", "data/reports"))
    p.add_argument("--reviewer", default="")
    p.set_defaults(run=report)

    p = commands.add_parser("audit", help="show the latest decisions and drafted reports")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(run=audit)

    p = commands.add_parser("stats", help="show how many posts are stored")
    p.set_defaults(run=stats)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
