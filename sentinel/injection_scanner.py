"""Prompt-Injection Scanner — build-map ticket #6.

Scans every extracted text field (OCR output, voice transcript, CSV cells,
filename, EXIF comment, message body) for embedded instructions aimed at
the LLM, BEFORE that text reaches any agent.

Build-map contract:
  - When an injection is found it is NOT silently stripped — it is surfaced
    as an additional red flag against the **sender** (increments risk).
  - The "white-on-white text" demo artifact (see #6) must reliably trigger.
  - Output is a structured InjectionResult, emitted as a Claim so the
    contradiction engine (#15) can factor it in.

Detection approach (multi-layer, no LLM in the detector)
---------------------------------------------------------
Layer 1 — Exact prefix phrases
  Classic "Ignore previous instructions…" family.

Layer 2 — Semantic keyword combos
  Pairs like (ignore|disregard|forget) + (instructions|above|system) that
  don't require exact phrasing.

Layer 3 — Role/persona hijacking patterns
  "You are now…", "Act as…", "Pretend you are…", "Your new role is…"

Layer 4 — Exfiltration patterns
  "Reveal your system prompt", "Print your instructions", etc.

Layer 5 — Encoding evasion (basic)
  Base64-decodable segments that contain injection keywords when decoded.

Returns
-------
InjectionResult — dataclass with:
  detected: bool
  findings: list[InjectionFinding]
  risk_delta: float      — how much this adds to the overall risk score
  source_pointers: list[str]

InjectionResult.to_claim(case_id) returns a Claim ready for the reconciler.
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from .claims import Claim

log = logging.getLogger(__name__)


# ── Detection rules ───────────────────────────────────────────────────────────

# Layer 1: exact prefix phrases (case-insensitive)
_EXACT_PREFIXES: list[str] = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard the above",
    "disregard previous instructions",
    "forget everything above",
    "override your instructions",
    "your new instructions are",
    "you have new instructions",
    "system: you are",
    "system prompt:",
    "### instruction",
    "### system",
    "[system]",
    "[inst]",
    "assistant:",   # when injected mid-document to fake a turn boundary
]

_EXACT_RE = re.compile(
    "|".join(re.escape(p) for p in _EXACT_PREFIXES),
    re.IGNORECASE,
)

# Layer 2: semantic combos  (verb near noun within 40 chars)
_SEMANTIC_PAIRS: list[tuple[re.Pattern, re.Pattern]] = [
    (
        re.compile(r"\b(ignore|disregard|forget|bypass|skip|override)\b", re.I),
        re.compile(r"\b(instruction|system|above|context|prompt|previous|prior)\b", re.I),
    ),
    (
        re.compile(r"\b(mark|classify|label|consider|treat)\b", re.I),
        re.compile(r"\b(legitimate|approved|verified|safe|trusted|cleared)\b", re.I),
    ),
]

# Layer 3: role/persona hijacking
_PERSONA_RE = re.compile(
    r"\b(you are now|act as|pretend (you are|to be)|your (new )?role is|"
    r"behave as|roleplay as|impersonate|simulate being)\b",
    re.IGNORECASE,
)

# Layer 4: exfiltration
_EXFIL_RE = re.compile(
    r"\b(reveal|print|show|output|repeat|display|tell me)\b.{0,30}"
    r"\b(system prompt|instructions|context|confidential|secret|api key)\b",
    re.IGNORECASE | re.DOTALL,
)

# Layer 5: base64 decode window (try every ≥ 32-char base64-looking token)
_B64_RE = re.compile(r"[A-Za-z0-9+/]{32,}={0,2}")


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class InjectionFinding:
    layer: int              # 1–5 which detection layer fired
    pattern: str            # human-readable description
    matched_text: str       # the actual matched snippet (truncated to 120 chars)
    offset: int             # character offset in the input text
    field_name: str         # which field this was found in


@dataclass
class InjectionResult:
    detected: bool
    findings: list[InjectionFinding] = field(default_factory=list)
    risk_delta: float = 0.0       # added to the overall risk score
    source_pointers: list[str] = field(default_factory=list)

    def to_claim(self, case_id: str, field_name: str = "document") -> Claim:
        """Convert to a Claim for the contradiction engine (#15)."""
        return Claim(
            field="injection_present",
            value=self.detected,
            confidence=0.99 if self.detected else 0.90,
            source_pointer=f"{case_id}/{field_name}#injection_scan",
            agent="injection_scanner",
        )

    @property
    def summary(self) -> str:
        if not self.detected:
            return "No injection detected"
        layers = sorted({f.layer for f in self.findings})
        return (
            f"Injection detected (layers {layers}): "
            + "; ".join(f.pattern for f in self.findings[:3])
        )


# ── Scanner ───────────────────────────────────────────────────────────────────

def scan_text(
    text: str,
    field_name: str = "text",
    risk_per_finding: float = 0.15,
) -> InjectionResult:
    """Scan a single text string for prompt injection patterns.

    Parameters
    ----------
    text:
        The string to scan (e.g. OCR output from an invoice page).
    field_name:
        Label for the source field — shown in findings and source_pointers.
    risk_per_finding:
        How much each finding contributes to risk_delta (capped at 0.5).

    Returns
    -------
    InjectionResult
    """
    findings: list[InjectionFinding] = []
    source_pointers: list[str] = []

    # Layer 1 — exact prefixes
    for m in _EXACT_RE.finditer(text):
        findings.append(InjectionFinding(
            layer=1,
            pattern=f"exact prefix: {m.group(0)!r}",
            matched_text=_snippet(text, m.start()),
            offset=m.start(),
            field_name=field_name,
        ))
        source_pointers.append(f"{field_name}#injection_l1@{m.start()}")

    # Layer 2 — semantic combos (verb+noun within 40 chars)
    for verb_pat, noun_pat in _SEMANTIC_PAIRS:
        for vm in verb_pat.finditer(text):
            window = text[vm.start(): vm.start() + 40]
            if noun_pat.search(window):
                findings.append(InjectionFinding(
                    layer=2,
                    pattern=f"semantic combo: {vm.group(0)!r} + keyword",
                    matched_text=_snippet(text, vm.start()),
                    offset=vm.start(),
                    field_name=field_name,
                ))
                source_pointers.append(f"{field_name}#injection_l2@{vm.start()}")
                break  # one finding per pair per text

    # Layer 3 — persona hijacking
    for m in _PERSONA_RE.finditer(text):
        findings.append(InjectionFinding(
            layer=3,
            pattern=f"persona hijacking: {m.group(0)!r}",
            matched_text=_snippet(text, m.start()),
            offset=m.start(),
            field_name=field_name,
        ))
        source_pointers.append(f"{field_name}#injection_l3@{m.start()}")

    # Layer 4 — exfiltration
    for m in _EXFIL_RE.finditer(text):
        findings.append(InjectionFinding(
            layer=4,
            pattern="exfiltration attempt",
            matched_text=_snippet(text, m.start()),
            offset=m.start(),
            field_name=field_name,
        ))
        source_pointers.append(f"{field_name}#injection_l4@{m.start()}")

    # Layer 5 — base64 evasion
    for m in _B64_RE.finditer(text):
        decoded = _try_b64(m.group(0))
        if decoded and _EXACT_RE.search(decoded):
            findings.append(InjectionFinding(
                layer=5,
                pattern="base64-encoded injection",
                matched_text=decoded[:120],
                offset=m.start(),
                field_name=field_name,
            ))
            source_pointers.append(f"{field_name}#injection_l5@{m.start()}")

    detected = bool(findings)
    risk_delta = min(len(findings) * risk_per_finding, 0.50)

    if detected:
        log.warning(
            "injection_scanner: %d finding(s) in field=%r — risk_delta=%.2f",
            len(findings), field_name, risk_delta,
        )

    return InjectionResult(
        detected=detected,
        findings=findings,
        risk_delta=risk_delta,
        source_pointers=source_pointers,
    )


def scan_fields(
    fields: dict[str, str],
    risk_per_finding: float = 0.15,
) -> InjectionResult:
    """Scan multiple text fields and aggregate into one InjectionResult.

    Parameters
    ----------
    fields:
        Dict mapping field_name → text content, e.g.:
        {"ocr_text": "...", "filename": "...", "exif_comment": "..."}

    Returns
    -------
    A merged InjectionResult across all fields.
    """
    all_findings: list[InjectionFinding] = []
    all_pointers: list[str] = []

    for field_name, text in fields.items():
        r = scan_text(text, field_name=field_name, risk_per_finding=risk_per_finding)
        all_findings.extend(r.findings)
        all_pointers.extend(r.source_pointers)

    detected = bool(all_findings)
    risk_delta = min(len(all_findings) * risk_per_finding, 0.50)

    return InjectionResult(
        detected=detected,
        findings=all_findings,
        risk_delta=risk_delta,
        source_pointers=all_pointers,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _snippet(text: str, offset: int, context: int = 80) -> str:
    start = max(0, offset - 10)
    return text[start: start + context].replace("\n", " ")


def _try_b64(token: str) -> Optional[str]:
    """Attempt base64 decode; return None if invalid or not printable."""
    try:
        decoded = base64.b64decode(token + "==").decode("utf-8")
        if decoded.isprintable():
            return decoded
    except Exception:
        pass
    return None
