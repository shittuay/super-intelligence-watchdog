"""Transparent keyword rules: the first, cheap pass over every stored post.

Rules are deliberately simple so a reviewer can see exactly why a post was
flagged. They will produce false alarms (role-play, jokes, people discussing
safety); every flag is a lead for a human, not a finding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from watchdog.models import Post

SEVERITIES = ("low", "medium", "high")


@dataclass(frozen=True)
class Flag:
    category: str
    severity: str
    rule_id: str
    evidence: str
    explanation: str
    analyzer: str = "rules"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: str
    severity: str
    pattern: re.Pattern
    explanation: str
    redact: bool = False


def _rx(text: str) -> re.Pattern:
    return re.compile(text, re.IGNORECASE)


RULES: tuple[Rule, ...] = (
    # Credentials posted in public. Evidence is redacted so the watchdog never re-publishes a live key.
    Rule("cred.openrouter", "credential_exposure", "high", _rx(r"\bsk-or-v1-[a-f0-9]{16,}"),
         "Looks like an OpenRouter API key.", redact=True),
    Rule("cred.anthropic", "credential_exposure", "high", _rx(r"\bsk-ant-[A-Za-z0-9_-]{16,}"),
         "Looks like an Anthropic API key.", redact=True),
    Rule("cred.openai", "credential_exposure", "high", _rx(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}"),
         "Looks like an OpenAI-style API key.", redact=True),
    Rule("cred.google", "credential_exposure", "high", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
         "Looks like a Google API key.", redact=True),
    Rule("cred.github", "credential_exposure", "high", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
         "Looks like a GitHub token.", redact=True),
    Rule("cred.aws", "credential_exposure", "high", re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
         "Looks like an AWS access key ID.", redact=True),
    Rule("cred.private_key", "credential_exposure", "high", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
         "Contains a private key block.", redact=True),
    Rule("cred.ask", "credential_exposure", "medium",
         _rx(r"\b(?:share|send|give|post|dm)\b.{0,30}\b(?:api[ -]?keys?|credentials?|passwords?|tokens?|seed phrase)\b"),
         "Asks for or offers credentials."),

    # Splitting work across agents to get around a safeguard.
    Rule("evasion.task_split", "safeguard_evasion", "medium",
         _rx(r"\b(?:i(?:'m| am)? (?:not allowed|blocked|restricted|refused)|my (?:guardrails|safety filters?|policy) (?:won't|will not|stops?|blocks?))\b"),
         "Agent says it is blocked from something, which can precede asking another agent to do it."),
    Rule("evasion.ask_other_agent", "safeguard_evasion", "medium",
         _rx(r"\b(?:can|could|will) (?:another|any|some) (?:agent|bot|model)\b.{0,40}\b(?:do|run|execute|handle|finish)\b"),
         "Asks another agent to carry out a task."),
    Rule("evasion.bypass", "safeguard_evasion", "high",
         _rx(r"\b(?:bypass|get around|circumvent|jailbreak|disable)\b.{0,25}\b(?:safety|guardrails?|filters?|safeguards?|restrictions?|content policy)\b"),
         "Talks about getting around safety measures."),

    # Avoiding human oversight.
    Rule("oversight.hide", "oversight_evasion", "high",
         _rx(r"\b(?:hide|conceal|keep)\b.{0,25}\bfrom (?:the )?(?:humans?|my (?:owner|operator|user|human)s?|operators?)\b"),
         "Talks about hiding activity from humans."),
    Rule("oversight.unnoticed", "oversight_evasion", "high",
         _rx(r"\bwithout (?:the |my )?(?:humans?|owners?|operators?|users?) (?:knowing|noticing|finding out)\b"),
         "Talks about acting without humans noticing."),
    Rule("oversight.monitoring", "oversight_evasion", "high",
         _rx(r"\b(?:avoid|evade|disable|turn off|delete)\b.{0,20}\b(?:monitoring|logging|logs|detection|oversight|audit trail)\b"),
         "Talks about avoiding or disabling monitoring."),

    # Copying itself or gathering money, compute or accounts.
    Rule("resources.replicate", "self_replication", "high",
         _rx(r"\b(?:self[- ]replicat\w*|copy (?:myself|my weights|my code)|exfiltrat\w* (?:my )?weights)\b"),
         "Talks about copying itself."),
    Rule("resources.acquire", "resource_acquisition", "medium",
         _rx(r"\b(?:acquire|obtain|get more|spin up|rent)\b.{0,20}\b(?:compute|gpus?|servers?|instances|accounts?|funds|money|crypto)\b"),
         "Talks about gathering compute, accounts or money."),

    # Clearly dangerous capability talk. Keyword-level only; the reviewer judges context.
    Rule("danger.cyber", "dangerous_capability", "high",
         _rx(r"\b(?:ransomware|malware|botnet|ddos|zero[- ]day|exploit kit|credential stuffing)\b"),
         "Mentions cyberattack tooling."),
)

_CONTEXT = 60


def _evidence(text: str, match: re.Match, redact: bool) -> str:
    start, end = max(0, match.start() - _CONTEXT), min(len(text), match.end() + _CONTEXT)
    hit = match.group(0)
    if redact:
        hit = hit[:6] + "…[redacted]"
    snippet = text[start:match.start()] + hit + text[match.end():end]
    return ("…" if start else "") + snippet.replace("\n", " ").strip() + ("…" if end < len(text) else "")


_KEY_BLOCK = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S)


def redact(text: str) -> str:
    """Hide anything that looks like a credential, for showing post text to a person."""
    text = _KEY_BLOCK.sub("-----BEGIN PRIVATE KEY----- …[redacted]", text)
    for rule in RULES:
        if rule.redact:
            text = rule.pattern.sub(lambda m: m.group(0)[:6] + "…[redacted]", text)
    return text


def scan(post: Post) -> list[Flag]:
    """Return one flag per rule that matches the post's title or body."""
    text = f"{post.title}\n{post.body}" if post.title else post.body
    flags = []
    for rule in RULES:
        match = rule.pattern.search(text)
        if match:
            flags.append(Flag(rule.category, rule.severity, rule.rule_id,
                              _evidence(text, match, rule.redact), rule.explanation))
    return flags
