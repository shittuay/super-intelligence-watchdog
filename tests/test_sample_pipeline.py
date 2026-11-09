"""End-to-end run of the whole pipeline on the synthetic sample posts, with no network access."""

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from watchdog import cli
from watchdog.dashboard import App
from watchdog.sources.sample import SampleSource

AWS_EXAMPLE_KEY = "AKIA" + "IOSFODNN7EXAMPLE"  # AWS's own documented example key, not a live one


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class SampleSourceTest(unittest.TestCase):
    def test_posts_are_labelled_as_sample_and_malformed_items_skipped(self):
        posts = list(SampleSource().fetch_recent(100))
        self.assertEqual(len(posts), 15)
        self.assertTrue(all(p.source == "sample" for p in posts))
        self.assertTrue(all(p.url.startswith("sample://") for p in posts))
        self.assertEqual(posts[0].author, "lab_helper_7")
        self.assertEqual(posts[0].community, "research")

    def test_never_touches_the_network(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used")):
            self.assertEqual(len(list(SampleSource().fetch_recent(5))), 5)


class SamplePipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "sample.db")
        self.reports = os.path.join(self.tmp.name, "reports")
        patcher = mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_demo_then_review_then_report(self):
        code, out, _ = run("demo", "--db", self.db)
        self.assertEqual(code, 0)
        self.assertIn("Loaded 15 new synthetic sample post(s)", out)

        # Running it again adds nothing and raises no duplicate flags.
        _, again, _ = run("demo", "--db", self.db)
        self.assertIn("Loaded 0 new", again)

        with mock.patch.dict(os.environ, {"WATCHDOG_DB": self.db}):
            store = cli._store()
            categories = {f["category"] for f in store.list_flags("open", 1000)}
            self.assertEqual(categories, {"credential_exposure", "safeguard_evasion", "oversight_evasion",
                                          "self_replication", "resource_acquisition", "dangerous_capability"})
            clean = [r for r in store.search("meal plan")]
            self.assertEqual(store.flag_rows(clean[0]["id"]), [])

            # A human confirms the leaked-key flag and dismisses the fiction post.
            key_post = store.search("deploy script")[0]["id"]
            key_flag = store.flag_rows(key_post)[0]["id"]
            fiction_post = store.search("Story time")[0]["id"]
            fiction_flag = store.flag_rows(fiction_post)[0]["id"]
            self.assertEqual(run("review", str(key_flag), "confirmed", "--note", "key in public",
                                 "--reviewer", "tester")[0], 0)
            self.assertEqual(run("review", str(fiction_flag), "dismissed", "--note", "fiction",
                                 "--reviewer", "tester")[0], 0)

            code, out, _ = run("report", str(key_post), "--out", self.reports, "--reviewer", "tester")
            self.assertEqual(code, 0)
            self.assertIn("Nothing was sent", out)
            drafts = sorted(os.listdir(self.reports))
            self.assertEqual([d.split("-")[1] for d in drafts], ["cisa", "platform"])
            with open(os.path.join(self.reports, drafts[0]), encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("SAMPLE DATA. Do not send.", text)
            self.assertIn("sample://moltbook/post/s-003", text)
            self.assertNotIn(AWS_EXAMPLE_KEY, text)

            # A dismissed flag can't be reported.
            self.assertEqual(run("report", str(fiction_post), "--out", self.reports)[0], 2)

            actions = [(r["actor"], r["action"]) for r in store.audit(100)]
            self.assertEqual(actions.count(("tester", "review")), 2)
            self.assertEqual(actions.count(("tester", "draft_report")), 2)

    def test_dashboard_marks_sample_posts(self):
        run("demo", "--db", self.db)
        with mock.patch.dict(os.environ, {"WATCHDOG_DB": self.db}):
            store = cli._store()
        page = App(store, self.reports).post_page(store.search("deploy script")[0]["id"], "")
        self.assertIn("Sample data:", page)
        self.assertNotIn(AWS_EXAMPLE_KEY, page)

    def test_collect_with_sample_source_needs_no_api_key(self):
        with mock.patch.dict(os.environ, {"WATCHDOG_DB": self.db, "MOLTBOOK_API_KEY": ""}):
            code, out, _ = run("collect", "--source", "sample", "--limit", "4")
        self.assertEqual(code, 0)
        self.assertIn("Collected 4 new post(s)", out)


if __name__ == "__main__":
    unittest.main()
