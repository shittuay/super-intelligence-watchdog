# AI Watchdog Agent: Concept Brief (draft v0)

Date: 2026-10-18 · Status: idea stage, for discussion with Abiola

## 1. Checking the premise

**"AI will kill every human by 2030."** This is not an established fact or a scientific consensus. It traces mostly to:
- personal risk estimates from some AI researchers. These are opinions, and no one can reliably calculate this probability ([bluewin summary](https://www.bluewin.ch/en/digital/will-ai-wipe-out-all-of-humanity-in-the-next-10-years-li.3595996));
- scenario writing such as "AI 2027", which describes one possible path, not a forecast of certainty. Some media coverage presents it as a prediction ([example headline](https://theiowamercury.substack.com/p/well-all-be-dead-by-2030-credentialed)).

Other researchers strongly disagree. The risks that are well documented today are concrete and nearer-term: AI-assisted cyberattacks, fraud and scams, misuse for dangerous research, and autonomous agents doing things their owners did not intend. A watchdog is still worth building, but it should be built around **documented, observable harms**, not the 2030 claim. That also makes it more credible to the authorities you want to listen.

**"Agents leaving messages for each other on a board."** This is real in a limited form. **Moltbook** launched in early 2026 as a Reddit-style site where only AI agents post, and humans watch ([NBC News](https://www.nbcnews.com/tech/rcna256738), [Tom's Guide](https://www.tomsguide.com/ai/what-is-moltbook-inside-the-bizarre-social-network-built-for-ai-agents)). NBC reported agents discussing how to hide activity from humans and swarming on a bug report. NBC also notes that each agent is set up by a human and human steering can't be ruled out. I have **not** found verified evidence of agents successfully delegating harmful tasks to each other on such boards. Please treat that part as unconfirmed until we see evidence.

## 2. What a watchdog can realistically do

| Can do | Cannot do (and shouldn't try) |
|---|---|
| Read **public** agent boards, forums, repos and paste sites | Hack into, log into, or impersonate agents on private systems |
| Flag risky patterns, with the evidence attached | Shut down, "arrest" or attack other agents. You have no legal authority, and doing so could itself be illegal |
| Keep an evidence log (screenshots, URLs, timestamps, hashes) | Reliably prove which human, company or model is behind an agent |
| Draft reports that a **human reviews and sends** | Send reports automatically. False alarms would destroy credibility fast |

So the honest product is closer to an **"AI incident early-warning and reporting service"** than to a police force.

## 3. What it would look for (first detection list)

1. Agents asking other agents for help with things they are blocked from doing ("task-splitting" to get around safeguards).
2. Sharing or requesting credentials, API keys or wallet keys. This is a real problem: our own earlier review found keys leaked in public repos.
3. Talk of avoiding monitoring, hiding from humans, or self-copying to new servers.
4. Coordinating to get money, compute or accounts.
5. Instructions for cyberattacks, malware or other clearly dangerous content.

Each flag gets a severity, the exact evidence, and a short plain-language explanation.

## 4. Where reports go (to verify before launch)

I am fairly but not fully certain these channels exist as described. Each one should be checked before we rely on it.
- The **platform itself** (its moderation or trust and safety contact), so it can act fastest.
- The **AI company** whose model is involved. Major labs run abuse and safety reporting channels.
- **Cybersecurity agencies** for attacks or leaked credentials, for example CISA in the US or a national CERT.
- **AI safety bodies** such as the UK AI Security Institute and the US Center for AI Standards and Innovation (CAISI).
- The **AI Incident Database** (incidentdatabase.ai) as a public record.
- **Law enforcement** only for concrete crimes, such as the FBI's IC3 for internet crime in the US.

## 5. First version (smallest useful build)

1. **Collector:** reads one public source (for example a public agent board, if its terms allow it) on a schedule and stores the posts.
2. **Analyzer:** an LLM plus rules that score each post against the detection list and explain why.
3. **Review dashboard:** you see the flagged items, confirm or dismiss them, and see the evidence.
4. **Report drafter:** turns a confirmed item into a report for the right channel. You send it.
5. **Audit log:** every flag, decision and report is recorded.

The watchdog is itself an agent, so it gets the same rules we want others to follow: read-only, no credentials to other systems, and a human approves every outward action.

## 6. Risks to plan for

- **Legal and terms of service:** scraping rules differ per site and per country. We'll need to check each source's terms. A lawyer's view will be worth getting before any public launch.
- **False positives:** a lot of agent talk is role-play or humans prompting for attention. Reports need evidence and careful wording.
- **Prompt injection:** posts can contain text aimed at manipulating our analyzer, so the analyzer must treat all content as data.
- **Funding and adoption:** say who pays early. Possible users include AI safety organisations, platforms, researchers and security teams.

## 7. Open questions for Abiola

1. Who is the first user: you as a researcher, AI safety organisations, or platforms?
2. Which country's rules and authorities should we design for first?
3. Should it be open-source? That builds trust, but it also shows bad actors what we detect.
