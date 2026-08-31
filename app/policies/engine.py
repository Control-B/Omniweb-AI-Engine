"""Deterministic Policy Engine for Human-in-the-Loop Governance.

Evaluates proposed agent mutations against hard organizational policies:
- High-value refunds and credits
- Custom discounts exceeding authorized thresholds
- Subscription cancellations and account terminations
- Compliance and identity risk gates
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyEvaluationResult(BaseModel):
    decision: PolicyDecision
    reason: str
    rule_id: str
    threshold_value: float | None = None
    requested_value: float | None = None


class PolicyEngine:
    """Deterministic business rule evaluator for agent actions."""

    def evaluate_action(
        self,
        *,
        action: str,
        params: dict[str, Any],
        tenant_id: str,
        actor: str = "ai_agent",
    ) -> PolicyEvaluationResult:
        """Evaluate action against deterministic safety thresholds."""
        logger.info(f"[Policy Engine] Evaluating action='{action}' for actor='{actor}'")

        # Rule 1: High-Risk Refund Threshold
        if action == "request_refund":
            amount = float(params.get("amount", 0.0))
            threshold = settings.HIGH_RISK_CREDIT_THRESHOLD
            if amount > threshold:
                return PolicyEvaluationResult(
                    decision=PolicyDecision.REQUIRE_APPROVAL,
                    reason=f"Refund of ${amount:.2f} exceeds automatic approval limit of ${threshold:.2f}.",
                    rule_id="RULE_REFUND_LIMIT_EXCEEDED",
                    threshold_value=threshold,
                    requested_value=amount,
                )

        # Rule 2: Custom Discount Limit
        if action == "apply_discount":
            discount_pct = float(params.get("discount_percent", 0.0))
            if discount_pct > 15.0:
                return PolicyEvaluationResult(
                    decision=PolicyDecision.REQUIRE_APPROVAL,
                    reason=f"Discount of {discount_pct:.1f}% exceeds authorized 15% agent threshold.",
                    rule_id="RULE_DISCOUNT_THRESHOLD_EXCEEDED",
                    threshold_value=15.0,
                    requested_value=discount_pct,
                )

        # Rule 3: Account / Subscription Cancellation
        if action in ("cancel_subscription", "delete_account"):
            return PolicyEvaluationResult(
                decision=PolicyDecision.REQUIRE_APPROVAL,
                reason="Account termination or cancellation requires supervisor confirmation.",
                rule_id="RULE_SUBSCRIPTION_TERMINATION",
            )

        # Default: Allowed
        return PolicyEvaluationResult(
            decision=PolicyDecision.ALLOW,
            reason="Action is within standard operating parameters.",
            rule_id="RULE_STANDARD_PERMITTED",
        )


_policy_engine = PolicyEngine()


def get_policy_engine() -> PolicyEngine:
    """Singleton getter for the policy engine."""
    return _policy_engine
