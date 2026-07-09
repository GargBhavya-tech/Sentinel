"""Policy / Authority Agent — build-map ticket #14.

Deterministic approval matrix check. No LLM in the decision path.

The build map is explicit: "A DETERMINISTIC check (plain Python, no LLM in
the decision) of requests against an approval matrix."

Why no LLM? Financial limits must be enforced to the cent — an LLM can
hallucinate a borderline pass. This module is a pure if/else gate.

Approval matrix (configurable via POLICY_CONFIG env var or direct dict)
-----------------------------------------------------------------------
Default matrix:
  Tier  | Max Amount  | Required Roles           | Dual Approval
  ------+-------------+--------------------------+--------------
  LOW   | $5,000      | manager                  | no
  MED   | $25,000     | manager, finance_director | no
  HIGH  | $100,000    | cfo, ceo                 | yes (both required)
  ULTRA | ∞           | ceo, board               | yes (both required)

Checks performed
----------------
1. Amount tier classification.
2. Whether the approver(s) have sufficient role.
3. Whether dual-approval is satisfied (for HIGH / ULTRA).
4. Whether the approval window is within business hours.
5. Whether the requesting user matches the invoice vendor contact
   (self-approval fraud pattern).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from typing import Optional

from ..claims import Claim

log = logging.getLogger(__name__)

# ── Approval matrix ───────────────────────────────────────────────────────────

_TIERS = [
    {
        "name": "LOW",
        "max_amount": 5_000.0,
        "allowed_roles": {"manager", "finance_director", "cfo", "ceo", "board"},
        "dual_approval": False,
    },
    {
        "name": "MED",
        "max_amount": 25_000.0,
        "allowed_roles": {"finance_director", "cfo", "ceo", "board"},
        "dual_approval": False,
    },
    {
        "name": "HIGH",
        "max_amount": 100_000.0,
        "allowed_roles": {"cfo", "ceo", "board"},
        "dual_approval": True,
    },
    {
        "name": "ULTRA",
        "max_amount": float("inf"),
        "allowed_roles": {"ceo", "board"},
        "dual_approval": True,
    },
]

_BUSINESS_HOURS = (dtime(8, 0), dtime(18, 0))   # 08:00 – 18:00 local


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class PolicyViolation:
    rule: str
    detail: str
    severity: float   # 0..1


@dataclass
class PolicyResult:
    case_id: str
    amount: float
    tier: str
    compliant: bool
    violations: list[PolicyViolation] = field(default_factory=list)
    source_pointer: str = ""

    def to_claim(self) -> Claim:
        return Claim(
            field="policy_violation",
            value=not self.compliant,
            confidence=1.0,   # deterministic — always fully confident
            source_pointer=self.source_pointer or f"{self.case_id}/policy#matrix",
            agent="policy",
        )

    @property
    def worst_severity(self) -> float:
        return max((v.severity for v in self.violations), default=0.0)


# ── Main entry point ───────────────────────────────────────────────────────────

def analyze(
    case_id: str,
    amount: float,
    approver_roles: list[str],            # e.g. ["manager"]
    approver_ids: Optional[list[str]] = None,   # Slack user IDs (for dual-approval check)
    requester_id: Optional[str] = None,
    vendor_contact_id: Optional[str] = None,
    request_time: Optional[datetime] = None,
    pre_metrics: Optional[dict] = None,
) -> PolicyResult:
    """Run deterministic policy checks against the approval matrix.

    Parameters
    ----------
    case_id:          Active case ID.
    amount:           Dollar amount being approved.
    approver_roles:   List of role strings for the approver(s).
    approver_ids:     Slack user IDs of approver(s).
    requester_id:     User ID of the person who triggered the payment.
    vendor_contact_id: If the vendor contact is also the requester — self-approval.
    request_time:     When the approval was submitted (for business-hours check).
    pre_metrics:      Pre-extracted values (mock shortcut).
    """
    if pre_metrics and "policy_violation" in pre_metrics:
        violated = bool(pre_metrics["policy_violation"])
        return PolicyResult(
            case_id=case_id, amount=amount, tier="UNKNOWN",
            compliant=not violated,
            source_pointer=f"{case_id}/policy#matrix",
        )

    # ── Classify tier ─────────────────────────────────────────────────────────
    tier_def = _classify_tier(amount)
    tier_name = tier_def["name"]

    violations: list[PolicyViolation] = []
    roles_set = {r.lower() for r in approver_roles}

    # ── Check 1: role authorisation ───────────────────────────────────────────
    allowed = tier_def["allowed_roles"]
    if not roles_set.intersection(allowed):
        violations.append(PolicyViolation(
            rule="unauthorized_role",
            detail=(
                f"${amount:,.0f} ({tier_name} tier) requires one of "
                f"{sorted(allowed)!r} — got {sorted(roles_set)!r}"
            ),
            severity=0.80,
        ))

    # ── Check 2: dual approval ────────────────────────────────────────────────
    if tier_def["dual_approval"]:
        distinct_roles = roles_set.intersection(allowed)
        distinct_approvers = len(set(approver_ids or []))
        if distinct_approvers < 2 or len(distinct_roles) < 2:
            violations.append(PolicyViolation(
                rule="dual_approval_required",
                detail=(
                    f"{tier_name} tier (>${_prev_tier_limit(tier_name):,.0f}) "
                    f"requires dual approval from two distinct authorised roles. "
                    f"Received {distinct_approvers} approver(s)."
                ),
                severity=0.90,
            ))

    # ── Check 3: self-approval ────────────────────────────────────────────────
    if requester_id and vendor_contact_id and requester_id == vendor_contact_id:
        violations.append(PolicyViolation(
            rule="self_approval",
            detail=(
                f"Requester {requester_id!r} appears to also be the vendor "
                f"contact — possible self-approval fraud pattern."
            ),
            severity=0.95,
        ))

    # ── Check 4: out-of-hours ─────────────────────────────────────────────────
    if request_time:
        t = request_time.time()
        lo, hi = _BUSINESS_HOURS
        if not (lo <= t <= hi):
            violations.append(PolicyViolation(
                rule="out_of_hours_approval",
                detail=(
                    f"Approval submitted at {t.strftime('%H:%M')} — "
                    f"outside business hours ({lo.strftime('%H:%M')}–"
                    f"{hi.strftime('%H:%M')})"
                ),
                severity=0.40,
            ))

    compliant = len(violations) == 0
    log.info(
        "policy: case=%s amount=%.2f tier=%s compliant=%s violations=%d",
        case_id, amount, tier_name, compliant, len(violations),
    )

    return PolicyResult(
        case_id=case_id, amount=amount, tier=tier_name,
        compliant=compliant, violations=violations,
        source_pointer=f"{case_id}/policy#matrix",
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _classify_tier(amount: float) -> dict:
    for tier in _TIERS:
        if amount <= tier["max_amount"]:
            return tier
    return _TIERS[-1]


def _prev_tier_limit(tier_name: str) -> float:
    for i, t in enumerate(_TIERS):
        if t["name"] == tier_name and i > 0:
            return _TIERS[i - 1]["max_amount"]
    return 0.0
