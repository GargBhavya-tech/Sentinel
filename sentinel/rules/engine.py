"""Deterministic rule engine (build-map ticket #26).

This is PURELY deterministic Python — no LLM anywhere in the evaluation path.
Financial limits must be enforced to the cent; an LLM could hallucinate a pass.

Public API
----------
match_rules(claims, rules) -> Rule | None
    Returns the first enforced rule that fires on the given claims, or None.
    Also checks shadow rules and logs their results without blocking.

The engine is intentionally simple: ALL non-null conditions must be satisfied
for a rule to fire (AND semantics). This is defensible under questioning.
"""

from __future__ import annotations

import logging
from typing import Sequence

from ..claims import Claim
from .schema import Rule

log = logging.getLogger(__name__)


def match_rules(
    claims: list[Claim],
    rules: Sequence[Rule],
) -> Rule | None:
    """Check claims against a list of rules.

    Shadow rules are evaluated and logged but never block or short-circuit.
    Enforced rules ARE returned — the caller (pipeline.py) then skips the
    full contradiction engine for speed.

    Returns the first matching enforced rule, or None.
    """
    claims_dict = {c.field: c.value for c in claims}
    first_match: Rule | None = None

    for rule in rules:
        fired = _evaluate(rule, claims_dict)
        if rule.status == "shadow":
            if fired:
                log.info(
                    "Shadow rule %s WOULD fire on this case (description=%r)",
                    rule.rule_id[:8],
                    rule.description,
                )
            else:
                log.debug("Shadow rule %s did not fire.", rule.rule_id[:8])
        elif rule.status == "enforced":
            if fired:
                log.info(
                    "Enforced rule %s FIRED — skipping full engine (description=%r)",
                    rule.rule_id[:8],
                    rule.description,
                )
                if first_match is None:
                    first_match = rule
        else:
            log.warning("Rule %s has unknown status %r", rule.rule_id[:8], rule.status)

    return first_match


def _evaluate(rule: Rule, claims_dict: dict) -> bool:
    """Return True iff ALL non-null conditions in the rule are satisfied."""

    # ── ratio check ────────────────────────────────────────────────────────
    if rule.ratio_threshold is not None:
        visual = claims_dict.get("visual_total")
        structured = claims_dict.get("structured_total")
        if visual is not None and structured is not None:
            v, s = float(visual), float(structured)
            ratio = max(v, s) / max(min(v, s), 1e-9)
            if ratio < rule.ratio_threshold:
                return False
        else:
            # If we can't compute the ratio, condition is not satisfied
            return False

    # ── tone anomaly check ─────────────────────────────────────────────────
    if rule.tone_anomaly_threshold is not None:
        tone = float(claims_dict.get("tone_anomaly", 0.0))
        if tone < rule.tone_anomaly_threshold:
            return False

    # ── voice mismatch check ───────────────────────────────────────────────
    if rule.voice_mismatch_threshold is not None:
        voice = float(claims_dict.get("voice_mismatch", 0.0))
        if voice < rule.voice_mismatch_threshold:
            return False

    # ── domain age check ───────────────────────────────────────────────────
    if rule.domain_age_days_max is not None:
        age = int(claims_dict.get("domain_age_days", 99999))
        if age >= rule.domain_age_days_max:
            return False

    # ── injection check ────────────────────────────────────────────────────
    if rule.injection_present is not None:
        present = bool(claims_dict.get("injection_present", False))
        if present != rule.injection_present:
            return False

    # ── policy violation check ─────────────────────────────────────────────
    if rule.policy_violation is not None:
        violated = bool(claims_dict.get("policy_violation", False))
        if violated != rule.policy_violation:
            return False

    return True
