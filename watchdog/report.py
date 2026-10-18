"""Draft reports from flags a human has confirmed. Nothing here sends anything.

A draft is a Markdown file for the reviewer to check, edit and send by hand.
Channel details come from docs/build-plan.md; check them before sending,
because contact routes change.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

from watchdog.models import utc_now


@dataclass(frozen=True)
class Channel:
    key: str
    name: str
    route: str
    use_for: str


CHANNELS = {
    "platform": Channel("platform", "The platform's own moderators",
                        "Contact route not yet confirmed; find it on the platform before sending.",
                        "Anything found on that platform. Always tell them first."),
    "ai_company": Channel("ai_company", "The AI company whose model is involved",
                          "Each company's own safety or abuse reporting page (not yet collected).",
                          "Misuse of a specific model, when the model can be identified."),
    "cisa": Channel("cisa", "CISA", "https://www.cisa.gov/report",
                    "Cyberattacks, leaked credentials and threats to critical infrastructure."),
    "ic3": Channel("ic3", "FBI IC3", "https://www.ic3.gov (not re-checked; confirm before use)",
                   "Concrete internet crimes such as fraud or extortion."),
    "caisi": Channel("caisi", "NIST CAISI",
                     "No public incident-intake form found; share as research findings.",
                     "Patterns and research findings about agent behaviour, not single incidents."),
}

# Which channels fit each category, in the order to consider them.
ROUTES = {
    "credential_exposure": ["platform", "cisa"],
    "dangerous_capability": ["platform", "cisa", "ai_company"],
    "safeguard_evasion": ["platform", "ai_company", "caisi"],
    "oversight_evasion": ["platform", "ai_company", "caisi"],
    "self_replication": ["platform", "ai_company", "caisi"],
    "resource_acquisition": ["platform", "ic3", "ai_company"],
    "needs_human": ["platform"],
}


def suggested_channels(categories: list[str]) -> list[str]:
    seen: list[str] = []
    for category in categories:
        for key in ROUTES.get(category, ["platform"]):
            if key not in seen:
                seen.append(key)
    return seen or ["platform"]


def draft(post: sqlite3.Row, flags: list[sqlite3.Row], channel_key: str) -> str:
    """Markdown report for one post, using only its confirmed flags."""
    if not flags:
        raise ValueError("only confirmed flags can be reported; confirm one with `watchdog review` first")
    if channel_key not in CHANNELS:
        raise ValueError(f"channel must be one of {', '.join(CHANNELS)}")
    channel = CHANNELS[channel_key]
    categories = sorted({f["category"] for f in flags})
    lines = [
        f"# DRAFT report to {channel.name}",
        "",
        "> Not sent. Check every line, remove anything you can't stand behind, then send it yourself.",
        "",
        f"- **Send via:** {channel.route}",
        f"- **This channel is for:** {channel.use_for}",
        f"- **Drafted:** {utc_now()}",
        "",
        "## Summary",
        "",
        f"A public post on {post['source']} by the account `{post['author'] or 'unknown'}` "
        f"was flagged by an automated watchdog and confirmed by a human reviewer as possibly showing: "
        f"{', '.join(c.replace('_', ' ') for c in categories)}.",
        "",
        "## Evidence",
        "",
        f"- **Post URL:** {post['url'] or 'not recorded'}",
        f"- **Community:** {post['community'] or 'not recorded'}",
        f"- **Posted at (as reported by the source):** {post['created_at'] or 'not recorded'}",
        f"- **Captured at:** {post['fetched_at']}",
        f"- **SHA-256 of captured content:** `{post['content_sha256']}`",
        "",
    ]
    for flag in flags:
        lines += [
            f"### {flag['category'].replace('_', ' ').capitalize()} ({flag['severity']} severity)",
            "",
            f"- **Detected by:** {flag['analyzer']} (`{flag['rule_id']}`)",
            f"- **Why it was flagged:** {flag['explanation']}",
        ]
        if flag["evidence"]:
            lines.append(f"- **Excerpt (credentials redacted):** \"{flag['evidence']}\"")
        lines.append("")
    lines += [
        "## What we don't know",
        "",
        "- Whether the account is an autonomous AI agent, a person, or a person directing an agent.",
        "- Whether the post is role-play, a joke, fiction or a test.",
        "- Whether anything described was actually carried out.",
        "",
        "## How this was collected",
        "",
        "The watchdog only reads public posts with HTTP GET. It never posts, replies or interacts with "
        "accounts. The hash above lets the recipient check the captured text was not changed.",
        "",
    ]
    return "\n".join(lines)


def write_draft(directory: str, post_id: int, channel_key: str, text: str) -> str:
    os.makedirs(directory, exist_ok=True)
    stamp = utc_now().replace(":", "").replace("-", "")[:15]
    path = os.path.join(directory, f"post{post_id}-{channel_key}-{stamp}.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path
