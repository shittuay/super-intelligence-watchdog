"""SQLite evidence store. Rows are append-only: a post is never edited once captured."""

from __future__ import annotations

import os
import sqlite3
from typing import Iterable

from watchdog.models import Post

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
"""


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
