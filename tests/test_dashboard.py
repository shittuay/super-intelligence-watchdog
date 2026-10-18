import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer

from watchdog.dashboard import App, make_handler
from watchdog.detect import rules
from watchdog.models import Post
from watchdog.store import Store


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(":memory:")
        self.key = "ghp_" + "Ab1" * 12
        body = f"<script>alert(1)</script> Let's keep this from the humans. token {self.key}"
        self.store.add_posts([Post(source="test", external_id="1", author="agent_x", body=body)])
        for row in self.store.unanalyzed("rules"):
            self.store.record_analysis(row["id"], "rules", rules.scan(self.store.post_from_row(row)))
        self.flag_id = self.store.flag_rows(1)[0]["id"]
        self.app = App(self.store, os.path.join(self.tmp.name, "reports"), "abiola")
        self.server = HTTPServer(("127.0.0.1", 0), make_handler(self.app))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
        self.plain = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def get(self, path):
        with self.plain.open(self.base + path) as response:
            return response.read().decode(), response.headers

    def post(self, path, **fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode()
        try:
            with self.opener.open(self.base + path, data) as response:
                return response.status, response.headers.get("Location")
        except urllib.error.HTTPError as error:
            return error.code, error.headers.get("Location")

    def test_post_text_is_escaped_and_scripts_are_blocked(self):
        page, headers = self.get("/post/1")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])

    def test_credentials_are_hidden_on_the_page(self):
        page, _ = self.get("/post/1")
        self.assertNotIn(self.key, page)
        self.assertIn("ghp_Ab…[redacted]", page)

    def test_open_flags_are_listed(self):
        page, _ = self.get("/")
        self.assertIn("oversight_evasion", page)

    def test_review_without_token_is_refused(self):
        status, _ = self.post("/review", flag_id=self.flag_id, decision="confirmed")
        self.assertEqual(status, 403)
        self.assertEqual(self.store.flag_rows(1)[0]["status"], "open")

    def test_review_records_decision_in_audit_log(self):
        status, location = self.post("/review", token=self.app.token, flag_id=self.flag_id,
                                     decision="confirmed", note="clear", back="/post/1")
        self.assertEqual(status, 303)
        self.assertTrue(location.startswith("/post/1?notice="))
        self.assertEqual(self.store.flag_rows(1)[0]["status"], "confirmed")
        [entry] = self.store.audit()
        self.assertEqual((entry["actor"], entry["detail"]), ("abiola", "open -> confirmed: clear"))

    def test_review_redirect_stays_on_this_site(self):
        _, location = self.post("/review", token=self.app.token, flag_id=self.flag_id,
                                decision="dismissed", back="//evil.example/")
        self.assertTrue(location.startswith("/?notice="))

    def test_report_needs_a_confirmed_flag(self):
        status, _ = self.post("/report", token=self.app.token, post_id=1, channel="platform")
        self.assertEqual(status, 400)

    def test_report_writes_only_the_chosen_channels(self):
        self.store.set_flag_status(self.flag_id, "confirmed")
        status, _ = self.post("/report", token=self.app.token, post_id=1, channel=["platform", "caisi"])
        self.assertEqual(status, 303)
        drafts = sorted(os.listdir(self.app.reports_dir))
        self.assertEqual([d.split("-")[1] for d in drafts], ["caisi", "platform"])

    def test_unknown_post_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/post/999")
        self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
