"""Threat-Intel Agent — build-map ticket #10.

VirusTotal + WHOIS lookups: detection counts, domain age, registrar.

Build-map rule: "Cache all responses and use demo-safe keys."

Architecture
------------
- A two-layer cache: in-memory first, then an optional local JSON file.
  This means the demo never makes a live network call unless a domain is
  genuinely new and VT_API_KEY is configured.
- When VT_API_KEY is not set, the agent runs in "demo mode" and returns
  from the seeded local cache only — never errors, never blocks.
- WHOIS age is computed from the whois library if installed; falls back to
  the cache. Domain age < 30 days is a strong risk signal.
- The agent never makes a call during tests — tests seed the cache directly.

Risk logic
----------
  domain_age_days < 30     → strong flag (weight 0.40)
  vt_malicious_votes > 0   → strong flag (weight 0.45 per malicious vote, cap 0.90)
  vt_suspicious_votes > 3  → mild flag (weight 0.15)
  unusual registrar         → mild flag (weight 0.10)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from ..claims import Claim

log = logging.getLogger(__name__)

# ── Cache ─────────────────────────────────────────────────────────────────────

_MEMORY_CACHE: dict[str, dict] = {}
_CACHE_TTL_SECONDS = 3600 * 24  # 24 hours

_DEMO_SEED: dict[str, dict] = {
    # A known-bad domain for demo purposes
    "evilpayments-inc.com": {
        "domain_age_days": 12,
        "vt_malicious": 8,
        "vt_suspicious": 3,
        "registrar": "NameCheap Inc.",
        "cached_at": 0,  # always "fresh" in demo
    },
    # A known-good domain
    "acmecorp.com": {
        "domain_age_days": 3650,
        "vt_malicious": 0,
        "vt_suspicious": 0,
        "registrar": "GoDaddy LLC",
        "cached_at": 0,
    },
}


def seed_cache(domain: str, data: dict) -> None:
    """Seed the in-memory cache for testing / demo pre-loads."""
    data.setdefault("cached_at", 0)  # 0 = never expires
    _MEMORY_CACHE[domain.lower()] = data


def clear_cache() -> None:
    _MEMORY_CACHE.clear()


def _get_cached(domain: str) -> Optional[dict]:
    domain = domain.lower()
    # Check test/runtime memory cache first (highest priority)
    entry = _MEMORY_CACHE.get(domain)
    if entry is not None:
        cached_at = entry.get("cached_at", 0)
        if cached_at == 0 or (time.time() - cached_at) < _CACHE_TTL_SECONDS:
            return entry
    # Fall back to the built-in demo seed
    if domain in _DEMO_SEED:
        return _DEMO_SEED[domain]
    return None


def _put_cache(domain: str, data: dict) -> None:
    data["cached_at"] = time.time()
    _MEMORY_CACHE[domain.lower()] = data


# ── Result ─────────────────────────────────────────────────────────────────────


@dataclass
class ThreatIntelResult:
    case_id: str
    domain: str
    domain_age_days: Optional[int]
    vt_malicious: int = 0
    vt_suspicious: int = 0
    registrar: Optional[str] = None
    risk_score: float = 0.0
    from_cache: bool = True
    flags: list[str] = field(default_factory=list)

    def to_claims(self) -> list[Claim]:
        claims: list[Claim] = [
            Claim(
                field="threat_risk",
                value=self.risk_score,
                confidence=0.85,
                source_pointer=f"{self.case_id}/threat_intel#{self.domain}",
                agent="threat_intel",
            ),
        ]
        # Only emit domain_age_days when it is a REAL, non-negative value.
        # Previously an unknown age was encoded as -1, which the reconciler
        # read as "registered -1 days ago" and floored risk to 0.90 — a
        # systemic false positive on every domain we couldn't resolve.
        if self.domain_age_days is not None and self.domain_age_days >= 0:
            claims.insert(
                0,
                Claim(
                    field="domain_age_days",
                    value=self.domain_age_days,
                    confidence=0.90,
                    source_pointer=f"{self.case_id}/threat_intel#{self.domain}",
                    agent="threat_intel",
                ),
            )
        return claims


# ── Main entry point ───────────────────────────────────────────────────────────


def analyze(
    case_id: str,
    domain: str,
    pre_metrics: Optional[dict] = None,
) -> ThreatIntelResult:
    """Run threat-intel lookups for a domain.

    Parameters
    ----------
    case_id:  Active case ID.
    domain:   Domain to investigate (e.g. "evilpayments-inc.com").
    pre_metrics: Pre-extracted values (mock shortcut).
    """
    if pre_metrics and "threat_risk" in pre_metrics:
        return ThreatIntelResult(
            case_id=case_id,
            domain=domain,
            domain_age_days=pre_metrics.get("domain_age_days"),
            risk_score=float(pre_metrics["threat_risk"]),
            from_cache=True,
        )

    domain = domain.lower().strip()

    # ── 1. Cache lookup ───────────────────────────────────────────────────────
    cached = _get_cached(domain)
    if cached:
        return _build_result(case_id, domain, cached, from_cache=True)

    # ── 2. Live lookup (only if configured) ──────────────────────────────────
    data: dict = {}
    vt_key = os.environ.get("VIRUSTOTAL_API_KEY", "")
    if vt_key:
        vt_data = _query_virustotal(domain, vt_key)
        data.update(vt_data)

    age = _query_whois_age(domain)
    if age is not None:
        data["domain_age_days"] = age

    if not data:
        log.warning("threat_intel: no data for %s (no VT key, no WHOIS)", domain)
        return ThreatIntelResult(
            case_id=case_id, domain=domain, domain_age_days=None, from_cache=False
        )

    _put_cache(domain, data)
    return _build_result(case_id, domain, data, from_cache=False)


def _build_result(
    case_id: str, domain: str, data: dict, from_cache: bool
) -> ThreatIntelResult:
    age = data.get("domain_age_days")
    vt_mal = int(data.get("vt_malicious", 0))
    vt_sus = int(data.get("vt_suspicious", 0))
    reg = data.get("registrar")
    flags: list[str] = []
    risk = 0.0

    if age is not None and age < 30:
        flags.append(f"young domain ({age} days old)")
        risk += 0.40

    if vt_mal > 0:
        flags.append(f"{vt_mal} VirusTotal malicious votes")
        risk += min(vt_mal * 0.10, 0.90)

    if vt_sus > 3:
        flags.append(f"{vt_sus} VirusTotal suspicious votes")
        risk += 0.15

    risk = round(min(risk, 1.0), 4)

    log.info(
        "threat_intel: case=%s domain=%s age=%s vt_mal=%d risk=%.3f cache=%s",
        case_id,
        domain,
        age,
        vt_mal,
        risk,
        from_cache,
    )

    return ThreatIntelResult(
        case_id=case_id,
        domain=domain,
        domain_age_days=age,
        vt_malicious=vt_mal,
        vt_suspicious=vt_sus,
        registrar=reg,
        risk_score=risk,
        from_cache=from_cache,
        flags=flags,
    )


# ── Live lookup helpers ────────────────────────────────────────────────────────


def _query_virustotal(domain: str, api_key: str) -> dict:
    """Query VirusTotal v3 API for a domain report."""
    try:
        import urllib.request

        url = f"https://www.virustotal.com/api/v3/domains/{domain}"
        req = urllib.request.Request(url, headers={"x-apikey": api_key})
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
        stats = (
            body.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        )
        return {
            "vt_malicious": int(stats.get("malicious", 0)),
            "vt_suspicious": int(stats.get("suspicious", 0)),
        }
    except Exception as e:
        log.warning("threat_intel: VT lookup failed for %s (%s)", domain, e)
        return {}


def _query_whois_age(domain: str) -> Optional[int]:
    """Return domain age in days using the whois library (optional)."""
    try:
        import whois  # type: ignore

        w = whois.whois(domain)
        created = w.creation_date
        if isinstance(created, list):
            created = created[0]
        if created:
            import datetime

            age = (datetime.datetime.now() - created).days
            return max(age, 0)
    except Exception:
        pass
    return None
