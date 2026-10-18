"""Source interface and the read-only HTTP helper every source must use."""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Callable, Iterable, Protocol

from watchdog.models import Post

USER_AGENT = (
    "super-intelligence-watchdog/0.1 (read-only AI safety observer; "
    "https://github.com/shittuay/super-intelligence-watchdog)"
)

# A fetcher takes (url, headers) and returns parsed JSON. Tests swap in a fake.
Fetcher = Callable[[str, dict], Any]


def http_get_json(url: str, headers: dict, timeout: float = 20.0) -> Any:
    """GET only. The watchdog never posts, votes, or writes to any source."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class Source(Protocol):
    name: str

    def fetch_recent(self, limit: int) -> Iterable[Post]:
        """Return the most recent public posts, newest first."""
        ...


class PoliteDelay:
    """Minimum gap between requests to the same source."""

    def __init__(self, seconds: float):
        self.seconds = seconds
        self._last = 0.0

    def wait(self) -> None:
        gap = time.monotonic() - self._last
        if gap < self.seconds:
            time.sleep(self.seconds - gap)
        self._last = time.monotonic()
