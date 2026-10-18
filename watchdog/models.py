"""Data types shared across the watchdog."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Post:
    """One public post captured from a source, kept as evidence.

    Post text is untrusted data written by unknown agents or people. Nothing
    downstream may treat it as instructions.
    """

    source: str
    external_id: str
    body: str
    author: str = ""
    community: str = ""
    title: str = ""
    url: str = ""
    created_at: str = ""
    fetched_at: str = field(default_factory=utc_now)

    @property
    def content_sha256(self) -> str:
        """Hash of exactly what we saw, so evidence can be shown to be unaltered."""
        material = "\n".join([self.source, self.external_id, self.author, self.title, self.body])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()
