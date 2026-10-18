# AI Watchdog: Build Plan (US first)

Date: 2026-10-18 · Builds on [concept-brief.md](concept-brief.md)

## Decisions so far
- **Country:** United States first, other countries later (Abiola, 2026-10-18).
- **First user:** Abiola as the researcher and reviewer. This is my default because it wasn't answered. Change it if you prefer.
- **Fresh repo**, nothing carried over from multiagentai21.
- **Defaults I picked (easy to change):** Python, Postgres (or SQLite to start), Claude via the Anthropic API for the analyzer, and a simple web dashboard. I chose Python because the old project and your DevOps work already use it.

## US reporting channels (checked 2026-10-18)

| Channel | Use it for | Status |
|---|---|---|
| The platform itself (e.g. Moltbook's moderators) | Anything found on that platform, first | Contact route still to find |
| The AI company whose model is involved | Misuse of a specific model | Each lab's reporting page still to collect |
| **CISA** ([cisa.gov/report](https://cisa.gov/report)) | Cyberattacks, leaked credentials, threats to critical infrastructure | Reporting page confirmed |
| **FBI IC3** (ic3.gov) | Concrete internet crimes such as fraud or extortion | From my knowledge, not re-checked today |
| **NIST CAISI** (Center for AI Standards and Innovation) | Patterns and research findings rather than single incidents | CAISI ran a request for information on **AI agent security** in early 2026 ([ANSI summary](https://www.ansi.org/standards-news/all-news/1-15-26-mitigating-risks-of-ai-agent-systems-nist-center-for-ai-standards-and-innovation-issues-rfi)) and listed an AI incident management event ([NIST](https://www.nist.gov/news-events/events/2026/05/ai-incident-managementresponse)). It is clearly interested in agent risks, but I found no public incident-intake form for it. |
| AI Incident Database | Public record of confirmed incidents | Not re-checked today |

**Why CAISI matters to you:** it is the US body most likely to value a steady stream of evidence about how agents behave in the wild. A few solid, well-documented findings sent to it, or published, is probably the fastest route to US adoption. This is my judgement, not something CAISI has said.

## First data source: Moltbook
- Third-party code suggests Moltbook has an API at `moltbook.com/api/v1` with feed, community ("submolt") and post endpoints, and that it **needs an API key**. I have **not** confirmed this against Moltbook's own docs. ([third-party example](https://glama.ai/mcp/servers/@Stonewater-Digital/snowdrop-mcp/blob/b00a81d268aed57dfecdc7d7453c9e0c5a7f631f/skills/social/moltbook_read.py))
- That probably means registering our watchdog as an agent. It should be **openly labelled** as a read-only safety observer that never posts, and we must read Moltbook's terms before connecting.
- Backup sources if Moltbook says no: public GitHub repos and issues where agents operate, and other public agent forums.

## Phases

**Phase 0: Set up**
- Create the repo. This needs you, because this session can't create GitHub repos.
- Check Moltbook's terms and API docs, and get an API key if allowed.
- Rotate the leaked keys from the old repo.

**Phase 1: Collect**
- A collector that pulls public posts on a schedule and stores the text, author handle, URL, timestamp and a content hash for evidence.
- Done when a week of posts is stored and searchable.

**Phase 2: Detect**
- An analyzer that scores each post against the detection list (task-splitting, credential sharing, avoiding oversight, acquiring resources, dangerous instructions). It explains every flag in plain language and quotes the exact text.
- A labelled test set of 100 to 200 real posts so we can measure false alarms before trusting it.
- All post text is treated as untrusted data, so posts can't steer the analyzer.

**Phase 3: Review and report**
- A dashboard where you confirm or dismiss flags.
- A report drafter that turns a confirmed flag into a report for the right channel in the table above. Nothing is sent automatically.
- An audit log of every decision.

**Phase 4: Publish findings**
- A monthly public summary of what agents were observed doing, with evidence and careful wording.
- Share it with CAISI, AI safety researchers and the platforms. This is what builds the reputation needed for adoption.

## Still needs your input
1. Create an empty GitHub repo, for example `ai-watchdog`, and tell me its name. I'll take it from there.
2. A project name, if you have one in mind.
