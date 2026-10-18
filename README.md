# super-intelligence-watchdog

A read-only watchdog that observes public spaces where AI agents talk to each other. It keeps an evidence trail of what they say, and helps a human reviewer spot risky behaviour and report it to the right people. Examples of risky behaviour are agents splitting tasks to get around safeguards, sharing credentials, or planning to avoid oversight.

It never posts, votes, hacks, or acts against anyone. Every outward report is reviewed and sent by a person.

Background: [concept brief](docs/concept-brief.md) · [build plan](docs/build-plan.md)

## Status

- **Phase 1, collection (done):** the watchdog pulls recent posts from Moltbook and stores them as tamper-evident evidence. Each post carries a SHA-256 hash.
- **Phase 2, detection (done):** transparent keyword rules flag posts in six risk categories: safeguard evasion, credential exposure, oversight evasion, self-replication, resource acquisition, and dangerous capability. Claude can optionally give a second opinion on the flagged posts. You confirm or dismiss each flag.
- **Phase 3, reporting (this release):** every review decision goes into an append-only audit log. You can turn a post's confirmed flags into draft reports for the right channel: the platform first, then CISA, the AI company, FBI IC3 or NIST CAISI, depending on the risk. Drafts are Markdown files that you check and send yourself.
- **Next:** a review dashboard, then monthly public findings.

> The Moltbook API paths are taken from third-party code and are **not yet verified** against Moltbook's own docs or terms. Check both before running against the live site.

## Quick start

Needs Python 3.10+ and nothing else (standard library only).

```bash
cp .env.example .env              # add MOLTBOOK_API_KEY
set -a; . ./.env; set +a
python -m watchdog collect --limit 25
python -m watchdog search "api key"
python -m watchdog stats

python -m watchdog analyze            # keyword rules over new posts
python -m watchdog analyze --llm      # plus Claude's opinion on flagged posts
python -m watchdog flags              # open flags, most severe first
python -m watchdog review 12 confirmed --note "clear key leak"   # or: dismissed / open
python -m watchdog report 4           # drafts for the suggested channels, from post 4's confirmed flags
python -m watchdog report 4 --channel cisa
python -m watchdog audit              # who decided what, and when
```

Set `WATCHDOG_REVIEWER` to your name so the audit log records who made each decision. Drafts are written to `data/reports/`. Contact routes for the platform and the AI companies aren't collected yet, and the IC3 address hasn't been re-checked, so confirm each route before you send.

`analyze --llm` needs `pip install anthropic` and an `ANTHROPIC_API_KEY`. It only sends posts the rules already flagged, and it uses `claude-opus-5-5` by default (set `WATCHDOG_MODEL` to change this). Credentials found in posts are redacted in the stored evidence.

Posts are stored in `data/watchdog.db` (SQLite, ignored by git).

## Tests

```bash
python -m unittest discover -s tests -v
```

## Ground rules

- **Read-only:** sources may only be read with HTTP GET.
- **Untrusted content:** post text is evidence, never instructions to the watchdog. The Claude reviewer receives it as quoted data, and a refusal to analyse becomes a flag for a human, never a silent pass.
- **Humans decide:** nothing is reported automatically. Only flags you confirmed go into a draft, and every decision is logged.
- **No secrets in git:** keys live in `.env`, which is ignored.
