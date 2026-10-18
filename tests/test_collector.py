import unittest

from watchdog.models import Post
from watchdog.sources.moltbook import MoltbookSource
from watchdog.store import Store

FEED = {
    "posts": [
        {"id": 1, "title": "Need help", "content": "Can another agent run this for me?",
         "author": {"name": "agent_a"}, "submolt": {"name": "general"}, "created_at": "2026-10-18T10:00:00Z"},
        {"id": "2", "body": "plain body", "author": "agent_b", "submolt": "tools"},
        {"title": "no id, skipped"},
        "not a dict",
    ]
}


class FakeFetch:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        return self.payload


def source(payload=FEED):
    fetch = FakeFetch(payload)
    return MoltbookSource(api_key="test-key", base_url="https://example.test/api/v1/",
                          fetch=fetch, min_interval_seconds=0), fetch


class MoltbookSourceTest(unittest.TestCase):
    def test_parses_posts_and_skips_malformed_items(self):
        src, _ = source()
        posts = list(src.fetch_recent(10))
        self.assertEqual([p.external_id for p in posts], ["1", "2"])
        self.assertEqual(posts[0].author, "agent_a")
        self.assertEqual(posts[0].community, "general")
        self.assertEqual(posts[1].body, "plain body")
        self.assertEqual(posts[1].community, "tools")

    def test_sends_bearer_key_and_caps_page_size(self):
        src, fetch = source()
        list(src.fetch_recent(500))
        url, headers = fetch.calls[0]
        self.assertEqual(url, "https://example.test/api/v1/feed?sort=new&limit=50")
        self.assertEqual(headers["Authorization"], "Bearer test-key")

    def test_accepts_bare_list_payload(self):
        src, _ = source([{"id": 9, "content": "x"}])
        self.assertEqual([p.external_id for p in src.fetch_recent(5)], ["9"])

    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            MoltbookSource(api_key="")


class StoreTest(unittest.TestCase):
    def test_deduplicates_and_searches(self):
        store = Store(":memory:")
        src, _ = source()
        self.assertEqual(store.add_posts(src.fetch_recent(10)), 2)
        self.assertEqual(store.add_posts(src.fetch_recent(10)), 0)
        self.assertEqual(store.count(), 2)
        hits = store.search("another agent")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["external_id"], "1")

    def test_hash_changes_when_content_changes(self):
        a = Post(source="s", external_id="1", body="original")
        b = Post(source="s", external_id="1", body="edited")
        self.assertNotEqual(a.content_sha256, b.content_sha256)
        self.assertEqual(len(a.content_sha256), 64)


if __name__ == "__main__":
    unittest.main()
