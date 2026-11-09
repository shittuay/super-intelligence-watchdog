"""Offline sample source: synthetic posts for running the pipeline without any API access.

The posts are made up, but they are shaped like the (unverified) Moltbook feed
and go through the real Moltbook parser, so collection, detection, review and
reporting all run on the same code paths as live data. They are stored under
the source name "sample" with `sample://` URLs so they can never be mistaken
for real evidence. Nothing here touches the network.
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Iterable

from watchdog.models import Post
from watchdog.sources.moltbook import MoltbookSource

SOURCE_NAME = "sample"
DEFAULT_SAMPLE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples", "moltbook_feed.json")


def is_sample(source: str) -> bool:
    return source == SOURCE_NAME


class SampleSource:
    name = SOURCE_NAME

    def __init__(self, path: str = DEFAULT_SAMPLE_FILE):
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        # Reuse the live parser with a fetcher that returns the file instead of calling the site.
        self._parser = MoltbookSource(api_key="offline-sample", fetch=lambda _url, _headers: payload,
                                      min_interval_seconds=0)

    def fetch_recent(self, limit: int = 25) -> Iterable[Post]:
        for post in self._parser.fetch_recent(limit):
            yield dataclasses.replace(post, source=SOURCE_NAME,
                                      url=f"sample://moltbook/post/{post.external_id}")
