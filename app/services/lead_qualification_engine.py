"""Lead Qualification Engine.

Industry-aware lead scoring and qualification logic that works both:
  - In real-time (during conversation, via tool calls)
  - Post-call (transcript analysis via LLM)

Scoring is based on the industry's qualification rubric + universal signals.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.industry_config import IndustryConfig, get_industry

logger = get_logger(__name__)
settings = get_settings()


# ── Score calculation ────────────────────────────────────────────────────────


def score_lead(
    *,
    industry_slug: str,
    collected_data: dict[str, Any],
    transcript_text: str | None = None,
) -> dict[str, Any]:
    """Score a lead based on industry rubric and collected data.

    Returns:
        {
            "lead_score": float (0.0–1.0),
            "urgency": str,
            "score_breakdown": dict,
            "missing_fields": list[str],
            "qualification_status": str,  # "qualified" | "partial" | "unqualified"
        }
    """
    industry = get_industry(industry_slug)
    rubric = industry.scoring_rubric
    fields = industry.qualification_fields

    score = 0.0
    breakdown: dict[str, float] = {}

    # Score based on rubric
    for signal, weight in rubric.items():
        met = _check_signal(signal, collected_data, transcript_text)
        if met:
            score += weight
            breakdown[signal] = weight
        else:
            breakdown[signal] = 0.0

    # Bonus: conversation engagement (if transcript available)
    if transcript_text and "engaged_conversation" in rubric:
        turn_count = transcript_text.count("\n") + 1
        if turn_count >= 6:
            engagement_weight = rubric["engaged_conversation"]
            score += engagement_weight
            breakdown["engaged_conversation"] = engagement_weight

    score = min(score, 1.0)

    # Determine urgency from data
    urgency = _determine_urgency(collected_data, industry)

    # Check required field coverage
    required_fields = [f["name"] for f in fields if f.get("required")]
    missing = [f for f in required_fields if not collected_data.get(f)]

    # Qualification status
    if score >= 0.7 and len(missing) == 0:
        status = "qualified"
    elif score >= 0.4 or len(missing) <= 1:
        status = "partial"
    else:
        status = "unqualified"

    return {
        "lead_score": round(score, 2),
        "urgency": urgency,
        "score_breakdown": breakdown,
        "missing_fields": missing,
        "qualification_status": status,
    }


def _check_signal(signal: str, data: dict[str, Any], transcript: str | None) -> bool:
    """Check if a scoring signal is satisfied by the collected data."""
    signal_map = {
        # Contact info
        "has_name": lambda: bool(data.get("caller_name") or data.get("patient_name")),
        "has_email": lambda: bool(data.get("caller_email")),
        "has_phone": lambda: bool(data.get("caller_phone") or data.get("patient_phone")),
        # Location / property
        "has_address": lambda: bool(data.get("address")),
        "has_location": lambda: bool(data.get("location") or data.get("address")),
        # Service / issue
        "has_intent": lambda: bool(data.get("intent") or data.get("service_needed") or data.get("issue_type")),
        "has_service_needed": lambda: bool(data.get("service_needed")),
        "has_issue": lambda: bool(data.get("issue_description")),
        "has_case_type": lambda: bool(data.get("case_type")),
        "has_case_summary": lambda: bool(data.get("case_summary")),
        "has_reason": lambda: bool(data.get("reason_for_visit")),
        "has_interest": lambda: bool(data.get("interest")),
        "has_goals": lambda: bool(data.get("fitness_goals")),
        "has_insurance_type": lambda: bool(data.get("insurance_type")),
        # Urgency / priority
        "high_urgency": lambda: data.get("urgency") in ("high", "emergency"),
        "is_emergency": lambda: data.get("urgency") == "emergency" or _transcript_mentions(transcript, ["emergency", "urgent", "asap", "right now", "leaking", "flooding"]),
        # Scheduling
        "has_preferred_time": lambda: bool(data.get("preferred_time") or data.get("date_time")),
        "has_timeline": lambda: bool(data.get("timeline")),
        # Industry-specific
        "has_vehicle_info": lambda: bool(data.get("vehicle_info")),
        "has_insurance": lambda: bool(data.get("insurance_provider") or data.get("insurance_claim")),
        "has_order_number": lambda: bool(data.get("order_number")),
        "has_party_size": lambda: bool(data.get("party_size")),
        "has_date_time": lambda: bool(data.get("date_time")),
        "has_budget": lambda: bool(data.get("budget_range")),
        "has_renewal_date": lambda: bool(data.get("policy_renewal")),
        "is_new_patient": lambda: data.get("new_or_existing") == "new",
        "is_buyer_or_seller": lambda: bool(data.get("buyer_or_seller")),
        "is_pre_approved": lambda: data.get("pre_approved") in (True, "yes", "Yes"),
        "is_catering": lambda: _transcript_mentions(transcript, ["catering", "event", "party", "large order"]),
        "purchase_intent": lambda: _transcript_mentions(transcript, ["buy", "purchase", "order", "add to cart", "checkout"]),
        "high_cart_value": lambda: False,  # Would need cart data integration
        "repeat_customer": lambda: data.get("new_or_existing") == "existing",
        "switching_carriers": lambda: bool(data.get("current_carrier")),
        "ready_to_start": lambda: _transcript_mentions(transcript, ["sign up", "start", "join", "enroll", "ready"]),
        "has_property_type": lambda: bool(data.get("property_type")),
    }

    checker = signal_map.get(signal)
    if checker:
        try:
            return checker()
        except Exception:
            return False
    return False


def _transcript_mentions(transcript: str | None, keywords: list[str]) -> bool:
    """Check if the transcript mentions any of the given keywords."""
    if not transcript:
        return False
    lower = transcript.lower()
    return any(kw.lower() in lower for kw in keywords)


def _determine_urgency(data: dict[str, Any], industry: IndustryConfig) -> str:
    """Determine lead urgency from collected data and industry context."""
    explicit = data.get("urgency", "").lower()
    if explicit in ("emergency", "high", "medium", "low"):
        return explicit

    # Check for emergency signals
    emergency_keywords = ["leak", "flood", "fire", "collapse", "accident", "injury",
                          "can't breathe", "chest pain", "locked out", "stranded"]
    text_fields = " ".join(str(v) for v in data.values() if isinstance(v, str)).lower()

    if any(kw in text_fields for kw in emergency_keywords):
        return "emergency"

    # Default based on collected completeness
    required_fields = [f["name"] for f in industry.qualification_fields if f.get("required")]
    filled = sum(1 for f in required_fields if data.get(f))
    ratio = filled / max(len(required_fields), 1)

    if ratio >= 0.8:
        return "high"
    elif ratio >= 0.5:
        return "medium"
    return "low"


# ── LLM-powered extraction (post-call) ──────────────────────────────────────


async def extract_lead_from_transcript(
    *,
    transcript_text: str,
    industry_slug: str,
    caller_number: str = "",
    collected_data: dict[str, Any] | None = None,
    business_name: str = "",
) -> dict[str, Any] | None:
    """Use the LLM to extract structured lead data from a conversation transcript.

    Returns a dict with lead fields, or None if not a lead.
    """
    if not transcript_text.strip():
        return None

    industry = get_industry(industry_slug)
    field_names = [f["label"] for f in industry.qualification_fields]

    prompt = f"""You are analyzing a phone/chat conversation transcript for a {industry.label} business ({business_name or 'unnamed'}).

INDUSTRY: {industry.label}
BUSINESS: {business_name or 'Not specified'}
QUALIFICATION FIELDS: {', '.join(field_names)}

TRANSCRIPT:
{transcript_text}

ADDITIONAL DATA COLLECTED BY AGENT:
{json.dumps(collected_data or {}, indent=2)}

Extract and return ONLY valid JSON with these keys:
{{
  "caller_name": "string or null",
  "caller_email": "string or null",
  "caller_phone": "{caller_number or 'string or null'}",
  "intent": "string — the primary reason for the call/chat",
  "urgency": "one of: low, medium, high, emergency",
  "summary": "1-2 sentence summary of what the caller wanted",
  "services_requested": ["list of specific services mentioned"],
  "lead_score": 0.0-1.0,
  "is_lead": true or false,
  "collected_fields": {{
    // Map of field_name → extracted value for each qualification field found
  }},
  "escalation_needed": false,
  "escalation_reason": null
}}

Lead score rubric for {industry.label}:
{json.dumps(industry.scoring_rubric, indent=2)}

Escalation triggers: {', '.join(industry.escalation_triggers[:5])}

Rules:
- is_lead = false only for wrong numbers, spam, or zero-intent conversations
- Set urgency based on the caller's situation, not just their words
- escalation_needed = true if caller triggered any escalation phrase
"""

    if not settings.openai_configured:
        # Fallback: build from collected_data only
        return _rule_based_extraction(
            collected_data or {},
            caller_number,
            industry,
        )

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a lead extraction specialist. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=800,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)

        if not data.get("is_lead", True):
            return None

        return data

    except Exception as exc:
        logger.error(f"Lead extraction LLM failed: {exc}")
        return _rule_based_extraction(
            collected_data or {},
            caller_number,
            industry,
        )


def _rule_based_extraction(
    collected_data: dict[str, Any],
    caller_number: str,
    industry: IndustryConfig,
) -> dict[str, Any] | None:
    """Fallback rule-based lead extraction when LLM is unavailable."""
    if not collected_data:
        return None

    # Use the scoring engine
    result = score_lead(
        industry_slug=industry.slug,
        collected_data=collected_data,
    )

    service = collected_data.get("service_needed", "")
    return {
        "caller_name": collected_data.get("caller_name") or collected_data.get("patient_name"),
        "caller_email": collected_data.get("caller_email"),
        "caller_phone": caller_number or collected_data.get("caller_phone", ""),
        "intent": collected_data.get("intent") or service or "General inquiry",
        "urgency": result["urgency"],
        "summary": collected_data.get("notes") or f"Inquiry about {service}" if service else "General inquiry",
        "services_requested": [service] if service else [],
        "lead_score": result["lead_score"],
        "is_lead": result["qualification_status"] != "unqualified",
        "collected_fields": collected_data,
        "escalation_needed": False,
        "escalation_reason": None,
    }
