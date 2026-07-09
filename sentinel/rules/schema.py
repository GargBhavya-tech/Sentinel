"""Rule dataclass and JSON schema (build-map ticket #26).

A rule is a structured JSON object — NOT free text — so a deterministic engine
can evaluate it without any LLM involved. The schema is intentionally minimal
for the hackathon; it covers the axes the contradiction engine uses.

Schema
------
{
    "rule_id":          str (UUID),
    "source_case_id":   str,
    "status":           "shadow" | "enforced",
    "created_at":       ISO-8601 string,
    "conditions": {
        "ratio_threshold":          float | null,   # visual/structured ratio
        "tone_anomaly_threshold":   float | null,   # stylometric score
        "voice_mismatch_threshold": float | null,
        "domain_age_days_max":      int   | null,   # flag if age < this
        "injection_present":        bool  | null,
        "policy_violation":         bool  | null,
    },
    "verdict":          "FRAUD_LIKELY" | "REVIEW",
    "description":      str,           # human-readable summary
    "fingerprint":      str,           # SHA-256 of canonical conditions JSON
}

A case matches a rule when ALL non-null conditions are satisfied.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

RuleStatus = str  # "shadow" | "enforced"

_VALID_STATUSES = {"shadow", "enforced"}


@dataclass
class Rule:
    """One synthesized detection rule."""

    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_case_id: str = ""
    status: RuleStatus = "shadow"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ── conditions ──────────────────────────────────────────────────────────
    ratio_threshold: Optional[float] = None          # flag if visual/structured ratio >= this
    tone_anomaly_threshold: Optional[float] = None   # flag if tone_anomaly >= this
    voice_mismatch_threshold: Optional[float] = None # flag if voice_mismatch >= this
    domain_age_days_max: Optional[int] = None        # flag if domain_age_days < this
    injection_present: Optional[bool] = None         # flag if injection detected
    policy_violation: Optional[bool] = None          # flag if policy violated

    verdict: str = "FRAUD_LIKELY"
    description: str = ""

    @property
    def fingerprint(self) -> str:
        """SHA-256 of the canonical conditions — used for cross-org matching."""
        conditions = {
            "ratio_threshold": self.ratio_threshold,
            "tone_anomaly_threshold": self.tone_anomaly_threshold,
            "voice_mismatch_threshold": self.voice_mismatch_threshold,
            "domain_age_days_max": self.domain_age_days_max,
            "injection_present": self.injection_present,
            "policy_violation": self.policy_violation,
        }
        canonical = json.dumps(conditions, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "source_case_id": self.source_case_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "conditions": {
                "ratio_threshold": self.ratio_threshold,
                "tone_anomaly_threshold": self.tone_anomaly_threshold,
                "voice_mismatch_threshold": self.voice_mismatch_threshold,
                "domain_age_days_max": self.domain_age_days_max,
                "injection_present": self.injection_present,
                "policy_violation": self.policy_violation,
            },
            "verdict": self.verdict,
            "description": self.description,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        cond = d.get("conditions", {})
        return cls(
            rule_id=d.get("rule_id", str(uuid.uuid4())),
            source_case_id=d.get("source_case_id", ""),
            status=d.get("status", "shadow"),
            created_at=datetime.fromisoformat(d["created_at"])
            if "created_at" in d
            else datetime.now(timezone.utc),
            ratio_threshold=cond.get("ratio_threshold"),
            tone_anomaly_threshold=cond.get("tone_anomaly_threshold"),
            voice_mismatch_threshold=cond.get("voice_mismatch_threshold"),
            domain_age_days_max=cond.get("domain_age_days_max"),
            injection_present=cond.get("injection_present"),
            policy_violation=cond.get("policy_violation"),
            verdict=d.get("verdict", "FRAUD_LIKELY"),
            description=d.get("description", ""),
        )
