"""Tests for Policy / Authority Agent (#14).

All deterministic — no LLM, no network, no DB.
"""

from datetime import datetime

import pytest
from sentinel.agents.policy_agent import (
    PolicyResult,
    PolicyViolation,
    analyze,
    _classify_tier,
)


# ── Tier classification ───────────────────────────────────────────────────────

def test_tier_low_boundary():
    assert _classify_tier(4999.99)["name"] == "LOW"
    assert _classify_tier(5000.0)["name"] == "LOW"


def test_tier_med_boundary():
    assert _classify_tier(5000.01)["name"] == "MED"
    assert _classify_tier(25000.0)["name"] == "MED"


def test_tier_high_boundary():
    assert _classify_tier(25000.01)["name"] == "HIGH"
    assert _classify_tier(100000.0)["name"] == "HIGH"


def test_tier_ultra():
    assert _classify_tier(100000.01)["name"] == "ULTRA"
    assert _classify_tier(1_000_000.0)["name"] == "ULTRA"


# ── Role authorisation ────────────────────────────────────────────────────────

def test_low_tier_manager_is_compliant():
    result = analyze(
        case_id="c1",
        amount=3000.0,
        approver_roles=["manager"],
    )
    assert result.compliant is True
    assert result.violations == []


def test_med_tier_manager_insufficient():
    result = analyze(
        case_id="c2",
        amount=20_000.0,
        approver_roles=["manager"],    # manager cannot approve MED alone
    )
    assert result.compliant is False
    violation_rules = [v.rule for v in result.violations]
    assert "unauthorized_role" in violation_rules


def test_high_tier_cfo_with_dual_approval_compliant():
    result = analyze(
        case_id="c3",
        amount=80_000.0,
        approver_roles=["cfo", "ceo"],
        approver_ids=["U_CFO", "U_CEO"],
    )
    assert result.compliant is True


def test_high_tier_cfo_alone_fails_dual_approval():
    result = analyze(
        case_id="c4",
        amount=80_000.0,
        approver_roles=["cfo"],
        approver_ids=["U_CFO"],        # only one approver
    )
    assert result.compliant is False
    rules = [v.rule for v in result.violations]
    assert "dual_approval_required" in rules


def test_ultra_tier_requires_two_distinct_approvers():
    result = analyze(
        case_id="c5",
        amount=200_000.0,
        approver_roles=["ceo"],
        approver_ids=["U_CEO"],
    )
    assert result.compliant is False


# ── Self-approval detection ────────────────────────────────────────────────────

def test_self_approval_flagged():
    result = analyze(
        case_id="c6",
        amount=1000.0,
        approver_roles=["manager"],
        requester_id="U_ALICE",
        vendor_contact_id="U_ALICE",   # same person — self-approval
    )
    rules = [v.rule for v in result.violations]
    assert "self_approval" in rules
    assert result.worst_severity >= 0.90


def test_different_requester_and_vendor_ok():
    result = analyze(
        case_id="c7",
        amount=1000.0,
        approver_roles=["manager"],
        requester_id="U_ALICE",
        vendor_contact_id="U_BOB",
    )
    rules = [v.rule for v in result.violations]
    assert "self_approval" not in rules


# ── Out-of-hours check ────────────────────────────────────────────────────────

def test_out_of_hours_flagged():
    midnight = datetime(2026, 7, 9, 2, 30)   # 02:30 AM
    result = analyze(
        case_id="c8",
        amount=1000.0,
        approver_roles=["manager"],
        request_time=midnight,
    )
    rules = [v.rule for v in result.violations]
    assert "out_of_hours_approval" in rules


def test_business_hours_not_flagged():
    noon = datetime(2026, 7, 9, 12, 0)
    result = analyze(
        case_id="c9",
        amount=1000.0,
        approver_roles=["manager"],
        request_time=noon,
    )
    rules = [v.rule for v in result.violations]
    assert "out_of_hours_approval" not in rules


# ── Classic BEC scenario (build-map canonical example) ───────────────────────

def test_60k_non_cfo_raises_policy_violation():
    """The build-map example: $60k request from a non-CFO must be flagged."""
    result = analyze(
        case_id="c10",
        amount=60_000.0,
        approver_roles=["manager"],   # only manager — not authorised for HIGH tier
    )
    assert result.compliant is False
    # Should flag BOTH unauthorized_role AND dual_approval_required
    rules = {v.rule for v in result.violations}
    assert "unauthorized_role" in rules


# ── Severity + Claim output ───────────────────────────────────────────────────

def test_worst_severity_from_most_severe_violation():
    result = analyze(
        case_id="c11",
        amount=1000.0,
        approver_roles=["manager"],
        requester_id="U_X",
        vendor_contact_id="U_X",
    )
    assert result.worst_severity == 0.95  # self_approval


def test_to_claim_compliant():
    result = analyze(case_id="c12", amount=1000.0, approver_roles=["manager"])
    claim = result.to_claim()
    assert claim.field == "policy_violation"
    assert claim.value is False       # compliant → no violation
    assert claim.confidence == 1.0    # always deterministic
    assert claim.agent == "policy"


def test_to_claim_violation():
    result = analyze(case_id="c13", amount=60_000.0, approver_roles=["manager"])
    claim = result.to_claim()
    assert claim.value is True        # violation detected


# ── Pre-metrics shortcut ──────────────────────────────────────────────────────

def test_pre_metrics_shortcut():
    result = analyze(
        case_id="c14",
        amount=1000.0,
        approver_roles=[],
        pre_metrics={"policy_violation": True},
    )
    assert result.compliant is False
