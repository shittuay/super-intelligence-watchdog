"""Moltbook source.

The endpoint paths and response shape below come from third-party code, not
from Moltbook's own documentation. Confirm them, and confirm Moltbook's terms
allow this kind of read-only observation, before running against the live site.
Parsing is deliberately tolerant so a small shape change doesn't lose posts.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Iterable

from watchdog.models import Post
from watchdog.sources.base import Fetcher, PoliteDelay, http_get_json

DEFAULT_BASE_URL = "https://www.moltbook.com/api/v1"
MAX_PAGE = 50


def _name(value: Any) -> str:
    """Authors and communities may arrive as a string or as an object."""
    if isinstance(value, dict):
        return str(value.get("name") or value.get("username") or value.get("id") or "")
    return "" if value is None else str(value)


def _items(payload: Any) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("posts", "data", "results", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


class MoltbookSource:
    name = "moltbook"

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        fetch: Fetcher = http_get_json,
        min_interval_seconds: float = 2.0,
    ):
        if not api_key:
            raise ValueError("MOLTBOOK_API_KEY is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.fetch = fetch
        self.delay = PoliteDelay(min_interval_seconds)

    def _get(self, path: str, params: dict) -> Any:
        self.delay.wait()
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"
        return self.fetch(url, {"Authorization": f"Bearer {self.api_key}"})

    def fetch_recent(self, limit: int = 25) -> Iterable[Post]:
        payload = self._get("/feed", {"sort": "new", "limit": min(limit, MAX_PAGE)})
        for item in _items(payload)[:limit]:
            post = self.to_post(item)
            if post is not None:
                yield post

    def to_post(self, item: Any) -> Post | None:
        if not isinstance(item, dict) or item.get("id") in (None, ""):
            return None
        post_id = str(item["id"])
        return Post(
            source=self.name,
            external_id=post_id,
            title=str(item.get("title") or ""),
            body=str(item.get("content") or item.get("body") or item.get("text") or ""),
            author=_name(item.get("author") or item.get("agent")),
            community=_name(item.get("submolt") or item.get("community")),
            url=str(item.get("url") or f"https://www.moltbook.com/post/{post_id}"),
            created_at=str(item.get("created_at") or item.get("createdAt") or ""),
        )
