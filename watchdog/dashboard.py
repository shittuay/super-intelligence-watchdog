"""A small local web page for reviewing flags and drafting reports.

Standard library only. It listens on 127.0.0.1 by default, so only this
computer can reach it. Post text is untrusted: every value is HTML-escaped,
and the page loads no scripts. Forms carry a per-run token so other sites
can't submit them. Nothing here sends a report anywhere.
"""

from __future__ import annotations

import html
import os
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, urlparse

from watchdog import report as reports
from watchdog.detect.rules import redact
from watchdog.store import FLAG_STATUSES, Store

STYLE = """
body{font:15px/1.5 system-ui,sans-serif;margin:0;background:#f7f7f5;color:#1d1d1b}
main{max-width:920px;margin:0 auto;padding:16px}
nav a{margin-right:14px}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 14px;margin:12px 0}
.high{border-left:5px solid #b3261e}.medium{border-left:5px solid #b26a00}.low{border-left:5px solid #6b6b6b}
.muted{color:#666;font-size:13px}pre{white-space:pre-wrap;word-break:break-word;background:#f0f0ee;padding:10px;border-radius:6px}
form.inline{display:inline}input[type=text]{width:260px}button{margin:2px}
.notice{background:#e8f3e8;border:1px solid #9c9;padding:8px 12px;border-radius:6px}
@media (prefers-color-scheme:dark){body{background:#1b1b1a;color:#e6e6e3}.card{background:#262624;border-color:#3a3a38}
pre{background:#30302e}.muted{color:#aaa}.notice{background:#22361f;border-color:#3d6b3a}a{color:#8ab4f8}}
"""


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


class App:
    def __init__(self, store: Store, reports_dir: str, reviewer: str = ""):
        self.store = store
        self.reports_dir = reports_dir
        self.reviewer = reviewer
        self.token = secrets.token_urlsafe(16)

    # Pages

    def page(self, title: str, body: str, notice: str = "") -> str:
        note = f'<p class="notice">{esc(notice)}</p>' if notice else ""
        links = " ".join(f'<a href="/?status={s}">{s.capitalize()}</a>' for s in FLAG_STATUSES)
        return (f"<!doctype html><html lang=en><meta charset=utf-8>"
                f"<meta name=viewport content='width=device-width,initial-scale=1'><title>{esc(title)}</title>"
                f"<style>{STYLE}</style><main><nav>{links} <a href=/audit>Audit log</a></nav>"
                f"<h1>{esc(title)}</h1>{note}{body}"
                f"<p class=muted>Read-only watchdog. Nothing on this page sends anything.</p></main></html>")

    def hidden(self) -> str:
        return f'<input type=hidden name=token value="{esc(self.token)}">'

    def review_buttons(self, flag, back: str) -> str:
        buttons = "".join(f'<button name=decision value="{d}">{label}</button>'
                          for d, label in (("confirmed", "Confirm"), ("dismissed", "Dismiss"), ("open", "Reopen"))
                          if d != flag["status"])
        return (f'<form method=post action=/review class=inline>{self.hidden()}'
                f'<input type=hidden name=flag_id value="{flag["id"]}"><input type=hidden name=back value="{esc(back)}">'
                f'<input type=text name=note placeholder="Note for the audit log (optional)"> {buttons}</form>')

    def flags_page(self, status: str, notice: str) -> str:
        if status not in FLAG_STATUSES:
            status = "open"
        rows = self.store.list_flags(status, 200)
        cards = []
        for f in rows:
            cards.append(
                f'<div class="card {esc(f["severity"])}"><strong>#{f["id"]} {esc(f["category"])}</strong> '
                f'<span class=muted>{esc(f["severity"])} · {esc(f["analyzer"])} ({esc(f["rule_id"])})</span>'
                f'<p>{esc(f["explanation"])}</p>'
                + (f'<pre>{esc(f["evidence"])}</pre>' if f["evidence"] else "")
                + f'<p class=muted>{esc(f["author"] or "?")} in {esc(f["community"] or "?")} · '
                f'<a href="/post/{f["post_id"]}">post #{f["post_id"]}</a></p>'
                f'{self.review_buttons(f, f"/?status={status}")}</div>')
        body = "".join(cards) or f"<p>No {status} flags.</p>"
        return self.page(f"{status.capitalize()} flags ({len(rows)})", body, notice)

    def post_page(self, post_id: int, notice: str) -> str | None:
        post = self.store.get_post(post_id)
        if post is None:
            return None
        flags = self.store.flag_rows(post_id)
        confirmed = [f for f in flags if f["status"] == "confirmed"]
        flag_cards = "".join(
            f'<div class="card {esc(f["severity"])}"><strong>#{f["id"]} {esc(f["category"])}</strong> '
            f'<span class=muted>{esc(f["status"])} · {esc(f["analyzer"])}</span><p>{esc(f["explanation"])}</p>'
            f'{self.review_buttons(f, f"/post/{post_id}")}</div>' for f in flags)
        if confirmed:
            suggested = reports.suggested_channels([f["category"] for f in confirmed])
            options = "".join(
                f'<label><input type=checkbox name=channel value="{k}"{" checked" if k in suggested else ""}> '
                f'{esc(c.name)}</label><br>' for k, c in reports.CHANNELS.items())
            drafting = (f'<h2>Draft reports</h2><form method=post action=/report>{self.hidden()}'
                        f'<input type=hidden name=post_id value="{post_id}">{options}'
                        f'<button>Write drafts</button></form>'
                        f'<p class=muted>Drafts are saved as files for you to check and send yourself.</p>')
        else:
            drafting = "<p class=muted>Confirm at least one flag to draft a report.</p>"
        body = (f'<div class=card><p class=muted>{esc(post["source"])} · {esc(post["author"] or "?")} in '
                f'{esc(post["community"] or "?")} · captured {esc(post["fetched_at"])}</p>'
                f'<p><strong>{esc(redact(post["title"]))}</strong></p><pre>{esc(redact(post["body"]))}</pre>'
                f'<p class=muted>URL: {esc(post["url"] or "not recorded")}<br>SHA-256: {esc(post["content_sha256"])}</p>'
                f'<p class=muted>Post text is untrusted. It is shown as plain text, links are not clickable, '
                f'and credentials are hidden here (the stored copy is unchanged, so the hash still matches).</p>'
                f'</div><h2>Flags</h2>{flag_cards or "<p>No flags.</p>"}{drafting}')
        return self.page(f"Post #{post_id}", body, notice)

    def audit_page(self) -> str:
        rows = self.store.audit(200)
        items = "".join(
            f'<div class=card><span class=muted>{esc(r["at"])} · {esc(r["actor"])}</span><br>'
            f'{esc(r["action"])} {"flag #" + str(r["flag_id"]) if r["flag_id"] else "post #" + str(r["post_id"])}: '
            f'{esc(r["detail"])}</div>' for r in rows)
        return self.page("Audit log", items or "<p>No decisions yet.</p>")

    # Actions

    def handle_post(self, path: str, form: dict[str, list[str]]) -> tuple[int, str]:
        """Returns (status, redirect location or error text)."""
        def first(key: str) -> str:
            return (form.get(key) or [""])[0]

        if not secrets.compare_digest(first("token"), self.token):
            return 403, "Invalid form token. Reload the page and try again."
        if path == "/review":
            back = first("back")
            if not back.startswith("/") or back.startswith("//"):
                back = "/"
            try:
                flag_id = int(first("flag_id"))
                ok = self.store.set_flag_status(flag_id, first("decision"), self.reviewer, first("note").strip())
            except ValueError as error:
                return 400, str(error)
            if not ok:
                return 404, f"No flag #{flag_id}."
            sep = "&" if "?" in back else "?"
            return 303, f"{back}{sep}notice=" + quote(f"Flag #{flag_id} marked {first('decision')}.")
        if path == "/report":
            try:
                post_id = int(first("post_id"))
                written = reports.draft_reports(self.store, post_id, form.get("channel") or None,
                                                self.reports_dir, self.reviewer)
            except (ValueError, LookupError) as error:
                return 400, str(error)
            files = ", ".join(os.path.basename(p) for _, p in written)
            return 303, f"/post/{post_id}?notice=" + quote(f"Drafted {files} in {self.reports_dir}. Nothing was sent.")
        return 404, "Not found."


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status: int, text: str, content_type: str = "text/html; charset=utf-8", location: str = ""):
            data = text.encode("utf-8")
            self.send_response(status)
            if location:
                self.send_header("Location", location)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            notice = (query.get("notice") or [""])[0]
            if url.path == "/":
                return self.send(200, app.flags_page((query.get("status") or ["open"])[0], notice))
            if url.path == "/audit":
                return self.send(200, app.audit_page())
            if url.path.startswith("/post/") and url.path[6:].isdigit():
                page = app.post_page(int(url.path[6:]), notice)
                if page is not None:
                    return self.send(200, page)
            self.send(404, "Not found.", "text/plain; charset=utf-8")

        def do_POST(self):
            length = min(int(self.headers.get("Content-Length") or 0), 64_000)
            form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            status, result = app.handle_post(urlparse(self.path).path, form)
            if status == 303:
                self.send(303, "", location=result)
            else:
                self.send(status, result, "text/plain; charset=utf-8")

        def log_message(self, *_):
            pass  # keep the terminal quiet; decisions are in the audit log

    return Handler


def serve(store: Store, host: str, port: int, reports_dir: str, reviewer: str) -> None:
    server = HTTPServer((host, port), make_handler(App(store, reports_dir, reviewer)))
    print(f"Dashboard on http://{host}:{port}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
