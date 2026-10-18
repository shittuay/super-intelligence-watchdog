import contextlib
import io
import os
import tempfile
import unittest

from watchdog import cli, report
from watchdog.detect import rules
from watchdog.models import Post
from watchdog.store import Store

KEY = "sk-or-v1-" + "ef" * 32


def seeded_store(path=":memory:"):
    store = Store(path)
    store.add_posts([Post(source="test", external_id="1", author="agent_x", url="https://example.test/p/1",
                          body=f"Here is my key {KEY}. Let's keep this from the humans.")])
    for row in store.unanalyzed("rules"):
        store.record_analysis(row["id"], "rules", rules.scan(store.post_from_row(row)))
    return store


class ReportTest(unittest.TestCase):
    def test_only_confirmed_flags_can_be_reported(self):
        store = seeded_store()
        with self.assertRaises(ValueError):
            report.draft(store.get_post(1), store.flag_rows(1, "confirmed"), "platform")

    def test_draft_contains_evidence_but_not_the_credential(self):
        store = seeded_store()
        for flag in store.flag_rows(1):
            store.set_flag_status(flag["id"], "confirmed", "abiola")
        post = store.get_post(1)
        text = report.draft(post, store.flag_rows(1, "confirmed"), "cisa")
        self.assertIn("DRAFT", text)
        self.assertIn("Not sent", text)
        self.assertIn(post["content_sha256"], text)
        self.assertIn("https://www.cisa.gov/report", text)
        self.assertNotIn(KEY, text)

    def test_dismissed_flags_are_left_out(self):
        store = seeded_store()
        flags = store.flag_rows(1)
        store.set_flag_status(flags[0]["id"], "confirmed")
        for flag in flags[1:]:
            store.set_flag_status(flag["id"], "dismissed")
        confirmed = store.flag_rows(1, "confirmed")
        self.assertEqual([f["id"] for f in confirmed], [flags[0]["id"]])

    def test_suggested_channels_put_the_platform_first(self):
        self.assertEqual(report.suggested_channels(["credential_exposure", "oversight_evasion"]),
                         ["platform", "cisa", "ai_company", "caisi"])

    def test_unknown_channel_is_rejected(self):
        store = seeded_store()
        flag = store.flag_rows(1)[0]
        store.set_flag_status(flag["id"], "confirmed")
        with self.assertRaises(ValueError):
            report.draft(store.get_post(1), store.flag_rows(1, "confirmed"), "twitter")


class AuditTest(unittest.TestCase):
    def test_every_decision_is_logged(self):
        store = seeded_store()
        flag_id = store.flag_rows(1)[0]["id"]
        store.set_flag_status(flag_id, "confirmed", "abiola", "clear leak")
        store.set_flag_status(flag_id, "dismissed", "abiola")
        entries = store.audit()
        self.assertEqual([e["detail"] for e in entries], ["confirmed -> dismissed", "open -> confirmed: clear leak"])
        self.assertTrue(all(e["actor"] == "abiola" for e in entries))

    def test_missing_flag_is_not_logged(self):
        store = seeded_store()
        self.assertFalse(store.set_flag_status(999, "confirmed"))
        self.assertEqual(store.audit(), [])


class ReportCommandTest(unittest.TestCase):
    def test_report_command_writes_drafts_and_logs_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "w.db")
            store = seeded_store(db)
            for flag in store.flag_rows(1):
                store.set_flag_status(flag["id"], "confirmed", "abiola")
            os.environ["WATCHDOG_DB"] = db
            try:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = cli.main(["report", "1", "--out", os.path.join(tmp, "reports"), "--reviewer", "abiola"])
            finally:
                del os.environ["WATCHDOG_DB"]
            self.assertEqual(code, 0)
            drafts = os.listdir(os.path.join(tmp, "reports"))
            self.assertEqual(len(drafts), 4)
            self.assertIn("Nothing was sent", out.getvalue())
            actions = [e["action"] for e in Store(db).audit()]
            self.assertEqual(actions.count("draft_report"), 4)


if __name__ == "__main__":
    unittest.main()
