# super-intelligence-watchdog

A read-only watchdog that observes public spaces where AI agents talk to each other. It keeps an evidence trail of what they say, and helps a human reviewer spot risky behaviour and report it to the right people. Examples of risky behaviour are agents splitting tasks to get around safeguards, sharing credentials, or planning to avoid oversight.

It never posts, votes, hacks, or acts against anyone. Every outward report is reviewed and sent by a person.

Background: [concept brief](docs/concept-brief.md) · [build plan](docs/build-plan.md)

## Status

Phase 1, collection. The watchdog can pull recent posts from Moltbook and store them as tamper-evident evidence (each post carries a SHA-256 hash), then search them. Detection, review and reporting come next.

> The Moltbook API paths are taken from third-party code and are **not yet verified** against Moltbook's own docs or terms. Check both before running against the live site.

## Quick start

Needs Python 3.10+ and nothing else (standard library only).

```bash
cp .env.example .env              # add MOLTBOOK_API_KEY
set -a; . ./.env; set +a
python -m watchdog collect --limit 25
python -m watchdog search "api key"
python -m watchdog stats
```

Posts are stored in `data/watchdog.db` (SQLite, ignored by git).

## Tests

```bash
python -m unittest discover -s tests -v
```

## Ground rules

- **Read-only:** sources may only be read with HTTP GET.
- **Untrusted content:** post text is evidence, never instructions to the watchdog.
- **Humans decide:** nothing is reported automatically.
- **No secrets in git:** keys live in `.env`, which is ignored.
