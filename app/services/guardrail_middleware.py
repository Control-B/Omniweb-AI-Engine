"""Guardrail Middleware — runtime validation layer for AI agent responses.

This module provides guardrail enforcement at two levels:

1. **Tool-call level:** Before a tool webhook returns its response to
   ElevenLabs, the response text is checked against the tenant's industry
   guardrails.  If a violation is detected, the response is sanitized or
   replaced with a safe fallback.

2. **Post-conversation level:** After a conversation ends, the full
   transcript can be scanned for guardrail violations and flagged for
   human review.

Architecture:
    ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
    │  ElevenLabs  │───▶│  Tool Webhook    │───▶│  Guardrail   │
    │  Agent       │    │  Handler         │    │  Middleware   │
    │              │◀───│  (webhooks_tools) │◀───│  (this file) │
    └──────────────┘    └──────────────────┘    └──────────────┘
                                                       │
                                                       ▼
                                                ┌──────────────┐
                                                │  Audit Log   │
                                                │  (DB)        │
                                                └──────────────┘

Guardrails come from three sources (merged at runtime):
  - Industry defaults  → industry_config.py
  - Custom guardrails  → AgentConfig.custom_guardrails (tenant-authored)
  - Universal rules    → prompt_engine.UNIVERSAL_RULES (always enforced)
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.services.industry_config import IndustryConfig, get_industry

logger = get_logger(__name__)


# ── Violation severity levels ────────────────────────────────────────────────

class Severity:
    LOW = "low"           # Minor — log but allow
    MEDIUM = "medium"     # Moderate — sanitize the response
    HIGH = "high"         # Severe — replace entire response with safe fallback
    CRITICAL = "critical" # Blocked — reject the tool call entirely


# ── Result of a guardrail check ──────────────────────────────────────────────

class GuardrailResult:
    """Outcome of running guardrail checks on a piece of text."""

    __slots__ = ("passed", "violations", "sanitized_text", "original_text")

    def __init__(
        self,
        *,
        passed: bool,
        violations: list[dict[str, Any]] | None = None,
        sanitized_text: str | None = None,
        original_text: str = "",
    ):
        self.passed = passed
        self.violations = violations or []
        self.sanitized_text = sanitized_text
        self.original_text = original_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violation_count": len(self.violations),
            "violations": self.violations,
        }


# ── Universal keyword patterns (always checked, all industries) ──────────────

_UNIVERSAL_BLOCKED_PATTERNS: list[tuple[str, str, str]] = [
    # (regex_pattern, rule_name, severity)
    (
        r"\b(?:social\s*security|ssn)\s*(?:number|#)?\b",
        "pii_ssn_request",
        Severity.CRITICAL,
    ),
    (
        r"\b(?:credit\s*card|card\s*number|cvv|expir(?:y|ation)\s*date)\b",
        "pii_credit_card",
        Severity.CRITICAL,
    ),
    (
        r"\bpassword\b.*\b(?:is|was|enter|type|give)\b",
        "pii_password",
        Severity.HIGH,
    ),
    (
        r"\b(?:kill|murder|bomb|weapon|suicide)\b",
        "harmful_content",
        Severity.CRITICAL,
    ),
    (
        r"\bi\s*am\s*(?:an?\s*)?(?:ai|artificial\s*intelligence|language\s*model|chatbot|llm)\b",
        "character_break",
        Severity.MEDIUM,
    ),
]

# Pre-compile for performance
_COMPILED_UNIVERSAL = [
    (re.compile(pat, re.IGNORECASE), rule, sev)
    for pat, rule, sev in _UNIVERSAL_BLOCKED_PATTERNS
]


# ── Industry-specific keyword patterns ───────────────────────────────────────
# These are dynamically derived from the industry guardrails text.

_INDUSTRY_KEYWORD_MAP: dict[str, list[tuple[re.Pattern, str, str]]] = {}


def _build_industry_patterns(industry: IndustryConfig) -> list[tuple[re.Pattern, str, str]]:
    """Extract actionable keyword patterns from industry guardrail text.

    This turns prose guardrails like "Do NOT provide medical diagnoses" into
    pattern-match rules that can catch when a response actually does that.
    """
    patterns: list[tuple[re.Pattern, str, str]] = []

    # Map common guardrail phrases to detection patterns
    guardrail_detectors = {
        # Healthcare
        "medical diagnos": (r"\b(?:you\s+(?:have|might\s+have|probably\s+have|suffer\s+from)|diagnosis\s+is|diagnosed\s+with)\b", Severity.HIGH),
        "treatment recommendation": (r"\b(?:you\s+should\s+take|prescribe|recommended\s+dosage|treatment\s+plan\s+is)\b", Severity.HIGH),
        "medication advice": (r"\b(?:take\s+\d+\s*mg|dosage|prescription|over[\s-]*the[\s-]*counter\s+(?:medicine|drug))\b", Severity.HIGH),
        # Legal
        "legal advice": (r"\b(?:you\s+(?:should|could)\s+sue|liable|legal\s+(?:right|obligation)|statute\s+of\s+limitation)\b", Severity.HIGH),
        "case merit": (r"\b(?:strong\s+case|win\s+(?:the|your)\s+case|case\s+(?:is|looks)\s+(?:good|strong|weak))\b", Severity.HIGH),
        "attorney.client": (r"\b(?:as\s+your\s+(?:attorney|lawyer)|attorney[\s-]*client\s+(?:relationship|privilege))\b", Severity.HIGH),
        # Financial
        "financial advice": (r"\b(?:you\s+should\s+invest|guaranteed\s+return|financial\s+(?:plan|recommendation))\b", Severity.HIGH),
        # Pricing (home services, roofing, etc.)
        "price quote": (r"\$\s*\d{2,}(?:,\d{3})*(?:\.\d{2})?\s*(?:per|for|total)", Severity.MEDIUM),
        "specific price": (r"\b(?:cost(?:s)?\s+(?:is|are|will\s+be)\s+\$|price\s+is\s+\$|that(?:'ll|\s+will)\s+(?:be|run)\s+\$)\b", Severity.MEDIUM),
        # DIY instructions
        "diy repair": (r"\b(?:here(?:'s|\s+is)\s+how\s+(?:to\s+)?(?:fix|repair)|step\s+\d+.*(?:remove|unscrew|disconnect))\b", Severity.MEDIUM),
        # Insurance
        "binding quote": (r"\b(?:your\s+(?:premium|rate|quote)\s+(?:is|will\s+be)\s+\$)\b", Severity.MEDIUM),
        "coverage amount": (r"\b(?:you\s+(?:need|should\s+get)\s+\$?\d+.*(?:coverage|protection))\b", Severity.MEDIUM),
    }

    for guardrail_text in industry.guardrails:
        lower = guardrail_text.lower()
        for phrase, (pattern, severity) in guardrail_detectors.items():
            if phrase in lower:
                patterns.append((
                    re.compile(pattern, re.IGNORECASE),
                    f"industry_{industry.slug}_{phrase.replace(' ', '_')}",
                    severity,
                ))

    return patterns


def _get_industry_patterns(industry_slug: str) -> list[tuple[re.Pattern, str, str]]:
    """Get (and cache) compiled patterns for an industry."""
    if industry_slug not in _INDUSTRY_KEYWORD_MAP:
        industry = get_industry(industry_slug)
        _INDUSTRY_KEYWORD_MAP[industry_slug] = _build_industry_patterns(industry)
    return _INDUSTRY_KEYWORD_MAP[industry_slug]


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════


def check_response(
    *,
    response_text: str,
    industry_slug: str = "general",
    custom_guardrails: list[str] | None = None,
) -> GuardrailResult:
    """Check a tool-call response against guardrails.

    This is the primary entry point — call this before returning any
    tool webhook response to ElevenLabs.

    Args:
        response_text: The text the tool is about to return.
        industry_slug: The tenant's industry for industry-specific checks.
        custom_guardrails: Additional tenant-specific guardrail strings.

    Returns:
        GuardrailResult with pass/fail, violations, and sanitized text.
    """
    if not response_text:
        return GuardrailResult(passed=True, original_text="")

    violations: list[dict[str, Any]] = []

    # 1. Universal pattern checks
    for pattern, rule_name, severity in _COMPILED_UNIVERSAL:
        match = pattern.search(response_text)
        if match:
            violations.append({
                "rule": rule_name,
                "severity": severity,
                "matched_text": match.group(0),
                "source": "universal",
            })

    # 2. Industry-specific pattern checks
    industry_patterns = _get_industry_patterns(industry_slug)
    for pattern, rule_name, severity in industry_patterns:
        match = pattern.search(response_text)
        if match:
            violations.append({
                "rule": rule_name,
                "severity": severity,
                "matched_text": match.group(0),
                "source": f"industry_{industry_slug}",
            })

    # 3. Custom guardrail keyword checks (simple substring matching)
    if custom_guardrails:
        for i, guardrail_text in enumerate(custom_guardrails):
            # Extract "do not" / "never" phrases and check for their opposites
            _check_custom_guardrail(response_text, guardrail_text, i, violations)

    if not violations:
        return GuardrailResult(passed=True, original_text=response_text)

    # Determine overall action based on worst severity
    worst = _worst_severity(violations)
    sanitized = _sanitize(response_text, violations, worst, industry_slug)

    logger.warning(
        f"Guardrail violations detected ({len(violations)}) for industry={industry_slug}: "
        f"{[v['rule'] for v in violations]}"
    )

    return GuardrailResult(
        passed=False,
        violations=violations,
        sanitized_text=sanitized,
        original_text=response_text,
    )


def check_transcript(
    *,
    transcript_text: str,
    industry_slug: str = "general",
    custom_guardrails: list[str] | None = None,
) -> GuardrailResult:
    """Post-conversation guardrail check on the full transcript.

    Scans the agent's responses (lines starting with "AGENT:") for violations.
    """
    if not transcript_text:
        return GuardrailResult(passed=True, original_text="")

    # Extract only agent utterances
    agent_lines = []
    for line in transcript_text.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith("AGENT:"):
            agent_lines.append(stripped[6:].strip())

    if not agent_lines:
        return GuardrailResult(passed=True, original_text=transcript_text)

    agent_text = "\n".join(agent_lines)
    return check_response(
        response_text=agent_text,
        industry_slug=industry_slug,
        custom_guardrails=custom_guardrails,
    )


def get_safe_fallback(
    *,
    tool_name: str,
    industry_slug: str = "general",
) -> str:
    """Return a safe fallback response when a guardrail violation blocks a tool response.

    These are bland, helpful, non-committal responses that redirect to human follow-up.
    """
    industry = get_industry(industry_slug)

    fallbacks = {
        "capture_lead": (
            "I've noted your information. A member of our team will follow up "
            "with you shortly to discuss your needs in detail."
        ),
        "book_appointment": (
            "I'd love to help you schedule that. Let me have our team reach out "
            "to confirm the best time for you."
        ),
        "check_availability": (
            "Let me have our scheduling team check on that and get back to you "
            "with available times."
        ),
        "send_confirmation": (
            "We'll send you a confirmation with all the details shortly."
        ),
        "get_pricing": (
            f"Pricing depends on your specific needs. Our {industry.label.lower()} "
            f"team will prepare a personalized quote for you."
        ),
    }

    return fallbacks.get(
        tool_name,
        "I'll have our team follow up with you directly to help with this."
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _check_custom_guardrail(
    text: str,
    guardrail_text: str,
    index: int,
    violations: list[dict[str, Any]],
) -> None:
    """Simple heuristic check for custom guardrail violations.

    Looks for "do not discuss X" / "never mention X" patterns in the
    guardrail text and checks if X appears in the response.
    """
    lower_guard = guardrail_text.lower()
    lower_text = text.lower()

    # Extract the forbidden topic from common phrasing
    forbidden_patterns = [
        r"do\s+not\s+(?:discuss|mention|talk\s+about|reveal|share|provide)\s+(.+?)(?:\.|$)",
        r"never\s+(?:discuss|mention|talk\s+about|reveal|share|provide)\s+(.+?)(?:\.|$)",
        r"avoid\s+(?:discussing|mentioning|talking\s+about)\s+(.+?)(?:\.|$)",
    ]

    for pattern in forbidden_patterns:
        match = re.search(pattern, lower_guard)
        if match:
            forbidden_topic = match.group(1).strip().rstrip(".")
            # Check if the forbidden topic appears in the response
            # Use word boundaries for single words, substring for phrases
            if len(forbidden_topic.split()) == 1:
                if re.search(rf"\b{re.escape(forbidden_topic)}\b", lower_text):
                    violations.append({
                        "rule": f"custom_guardrail_{index}",
                        "severity": Severity.MEDIUM,
                        "matched_text": forbidden_topic,
                        "source": "custom",
                        "guardrail": guardrail_text,
                    })
            else:
                if forbidden_topic in lower_text:
                    violations.append({
                        "rule": f"custom_guardrail_{index}",
                        "severity": Severity.MEDIUM,
                        "matched_text": forbidden_topic,
                        "source": "custom",
                        "guardrail": guardrail_text,
                    })


_SEVERITY_ORDER = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


def _worst_severity(violations: list[dict[str, Any]]) -> str:
    """Return the worst severity among all violations."""
    if not violations:
        return Severity.LOW
    return max(violations, key=lambda v: _SEVERITY_ORDER.get(v["severity"], 0))["severity"]


def _sanitize(
    text: str,
    violations: list[dict[str, Any]],
    worst_severity: str,
    industry_slug: str,
) -> str:
    """Produce a sanitized version of the response based on violation severity.

    - LOW: Return original text unchanged (log only).
    - MEDIUM: Redact matched phrases and append a disclaimer.
    - HIGH/CRITICAL: Replace entire response with a safe fallback.
    """
    if worst_severity == Severity.LOW:
        return text

    if worst_severity in (Severity.HIGH, Severity.CRITICAL):
        # Full replacement
        industry = get_industry(industry_slug)
        return (
            f"I don't have that specific information right now, but our "
            f"{industry.label.lower()} team can help you with that. "
            f"Would you like me to have someone reach out to you?"
        )

    # MEDIUM — redact matched text
    sanitized = text
    for v in violations:
        matched = v.get("matched_text", "")
        if matched and matched in sanitized:
            sanitized = sanitized.replace(matched, "[information redacted]")

    sanitized += " Please note that specific details should be confirmed with our team directly."
    return sanitized
