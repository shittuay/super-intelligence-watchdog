"""SQLite evidence store. Rows are append-only: a post is never edited once captured."""

from __future__ import annotations

import os
import sqlite3
from typing import Iterable

from watchdog.detect.rules import Flag
from watchdog.models import Post, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    author TEXT NOT NULL,
    community TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    UNIQUE (source, external_id)
);
CREATE INDEX IF NOT EXISTS posts_fetched_at ON posts (fetched_at);

-- One row per (post, analyzer) once that analyzer has looked at the post.
CREATE TABLE IF NOT EXISTS analyses (
    post_id INTEGER NOT NULL REFERENCES posts (id),
    analyzer TEXT NOT NULL,
    analyzed_at TEXT NOT NULL,
    PRIMARY KEY (post_id, analyzer)
);

-- A flag is a lead for the human reviewer. Only its status ever changes.
CREATE TABLE IF NOT EXISTS flags (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts (id),
    analyzer TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    evidence TEXT NOT NULL,
    explanation TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'confirmed', 'dismissed')),
    created_at TEXT NOT NULL,
    UNIQUE (post_id, analyzer, rule_id, category)
);

-- Append-only record of every human decision and every report drafted.
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    flag_id INTEGER,
    post_id INTEGER,
    detail TEXT NOT NULL
);
"""

FLAG_STATUSES = ("open", "confirmed", "dismissed")


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add_posts(self, posts: Iterable[Post]) -> int:
        """Store posts not seen before. Returns how many were new."""
        added = 0
        with self.db:
            for post in posts:
                cursor = self.db.execute(
                    "INSERT OR IGNORE INTO posts (source, external_id, author, community, title, body,"
                    " url, created_at, fetched_at, content_sha256) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (post.source, post.external_id, post.author, post.community, post.title,
                     post.body, post.url, post.created_at, post.fetched_at, post.content_sha256),
                )
                added += cursor.rowcount
        return added

    def search(self, text: str, limit: int = 20) -> list[sqlite3.Row]:
        pattern = f"%{text}%"
        return self.db.execute(
            "SELECT * FROM posts WHERE title LIKE ? OR body LIKE ? ORDER BY fetched_at DESC LIMIT ?",
            (pattern, pattern, limit),
        ).fetchall()

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

    def post_from_row(self, row: sqlite3.Row) -> Post:
        return Post(source=row["source"], external_id=row["external_id"], body=row["body"],
                    author=row["author"], community=row["community"], title=row["title"],
                    url=row["url"], created_at=row["created_at"], fetched_at=row["fetched_at"])

    def unanalyzed(self, analyzer: str, limit: int = 1000) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT p.* FROM posts p WHERE NOT EXISTS (SELECT 1 FROM analyses a"
            " WHERE a.post_id = p.id AND a.analyzer = ?) ORDER BY p.id LIMIT ?",
            (analyzer, limit),
        ).fetchall()

    def record_analysis(self, post_id: int, analyzer: str, flags: Iterable[Flag]) -> int:
        """Store an analyzer's flags for a post and mark it done. Returns new flags added."""
        now = utc_now()
        added = 0
        with self.db:
            for flag in flags:
                cursor = self.db.execute(
                    "INSERT OR IGNORE INTO flags (post_id, analyzer, rule_id, category, severity,"
                    " evidence, explanation, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (post_id, flag.analyzer, flag.rule_id, flag.category, flag.severity,
                     flag.evidence, flag.explanation, now),
                )
                added += cursor.rowcount
            self.db.execute("INSERT OR IGNORE INTO analyses (post_id, analyzer, analyzed_at) VALUES (?,?,?)",
                            (post_id, analyzer, now))
        return added

    def flagged_posts_without(self, analyzer: str, limit: int = 100) -> list[sqlite3.Row]:
        """Posts that have open flags but haven't been seen by `analyzer` yet."""
        return self.db.execute(
            "SELECT DISTINCT p.* FROM posts p JOIN flags f ON f.post_id = p.id AND f.status = 'open'"
            " WHERE NOT EXISTS (SELECT 1 FROM analyses a WHERE a.post_id = p.id AND a.analyzer = ?)"
            " ORDER BY p.id LIMIT ?",
            (analyzer, limit),
        ).fetchall()

    def flags_for(self, post_id: int) -> list[Flag]:
        rows = self.db.execute("SELECT * FROM flags WHERE post_id = ?", (post_id,)).fetchall()
        return [Flag(r["category"], r["severity"], r["rule_id"], r["evidence"], r["explanation"], r["analyzer"])
                for r in rows]

    def list_flags(self, status: str = "open", limit: int = 50) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT f.*, p.source, p.author, p.community, p.url, p.content_sha256 FROM flags f"
            " JOIN posts p ON p.id = f.post_id WHERE f.status = ?"
            " ORDER BY CASE f.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, f.id"
            " LIMIT ?",
            (status, limit),
        ).fetchall()

    def set_flag_status(self, flag_id: int, status: str, actor: str = "", note: str = "") -> bool:
        """Record a reviewer's decision on a flag, and log it. Returns False if there is no such flag."""
        if status not in FLAG_STATUSES:
            raise ValueError(f"status must be one of {', '.join(FLAG_STATUSES)}")
        with self.db:
            row = self.db.execute("SELECT post_id, status FROM flags WHERE id = ?", (flag_id,)).fetchone()
            if row is None:
                return False
            self.db.execute("UPDATE flags SET status = ? WHERE id = ?", (status, flag_id))
            detail = f"{row['status']} -> {status}" + (f": {note}" if note else "")
            self._log(actor, "review", detail, flag_id, row["post_id"])
        return True

    def get_post(self, post_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()

    def flag_rows(self, post_id: int, status: str | None = None) -> list[sqlite3.Row]:
        query, params = "SELECT * FROM flags WHERE post_id = ?", [post_id]
        if status:
            query, params = query + " AND status = ?", params + [status]
        return self.db.execute(query + " ORDER BY id", params).fetchall()

    def log(self, actor: str, action: str, detail: str, flag_id: int | None = None,
            post_id: int | None = None) -> None:
        with self.db:
            self._log(actor, action, detail, flag_id, post_id)

    def _log(self, actor, action, detail, flag_id, post_id) -> None:
        self.db.execute("INSERT INTO audit_log (at, actor, action, flag_id, post_id, detail) VALUES (?,?,?,?,?,?)",
                        (utc_now(), actor or "unknown", action, flag_id, post_id, detail))

    def audit(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
