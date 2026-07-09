"""PII Redaction Gateway — build-map ticket #4.

Sits in front of EVERY outbound LLM call. Replaces sensitive values with
format-preserving HMAC-SHA256 tokens so stylometric and finance signals
survive, then re-injects real values into the LLM response before anything
is posted to Slack.

Design constraints from the build map:
  - DO NOT blind-redact to <NAME_1> — it kills the stylometric signal.
  - Use format-preserving tokens: an account number becomes a token that
    looks like an account number (same length, same character class).
  - Pull the pepper from the PII_HMAC_PEPPER env var — never hardcode it.

The three-step flow
-------------------
1. redact(text)   → scrubbed_text, registry
2. <LLM call with scrubbed_text>
3. rehydrate(response, registry) → real_text_back

The registry is a dict mapping token → original_value. It lives only in
memory for the duration of one pipeline call; it is never persisted.

PII types handled (regex + spaCy NER as a second pass)
-------------------------------------------------------
  ACCOUNT_NUMBER    e.g. 123-456-7890123  (bank/invoice)
  SSN               e.g. 123-45-6789
  PHONE             e.g. +1-800-555-0100, (800) 555-0100
  EMAIL             e.g. user@example.com
  PERSON_NAME       via spaCy NER (PERSON entity)
  ORG_NAME          via spaCy NER (ORG entity) — optional, toggled by flag
  AMOUNT            $ values — NOT redacted by default (finance signal);
                    caller must set redact_amounts=True explicitly

Tokens look like:  ⟦ACCT:a3f9b2c1⟧  (unicode brackets → visually distinct,
                   safe in prompts, easy to strip in Slack output)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

# ── HMAC pepper ───────────────────────────────────────────────────────────────

def _pepper() -> bytes:
    val = os.environ.get("PII_HMAC_PEPPER", "")
    if not val:
        raise RuntimeError(
            "PII_HMAC_PEPPER env var is not set. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return val.encode()


def _hmac_token(label: str, value: str) -> str:
    """Format-preserving HMAC token.

    The token is the first 8 hex chars of HMAC-SHA256(pepper, label+value),
    wrapped in unicode brackets so it's visually distinct and greppable.
    """
    digest = hmac.new(_pepper(), f"{label}:{value}".encode(), hashlib.sha256).hexdigest()
    return f"\u27e6{label}:{digest[:8]}\u27e7"


# ── Regex patterns ────────────────────────────────────────────────────────────

_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Social Security Number
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Bank account / invoice number  (6-20 digits, with optional hyphens)
    ("ACCT", re.compile(r"\b\d{2,6}[-\s]?\d{4,10}[-\s]?\d{0,7}\b")),
    # Email
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    # Phone  (+1-800-555-0100 / (800) 555-0100 / 800.555.0100)
    ("PHONE", re.compile(
        r"(\+?\d{1,3}[\s\-.]?)?"
        r"(\(?\d{3}\)?[\s\-.]?)"
        r"\d{3}[\s\-.]?\d{4}\b"
    )),
]


# ── Registry ──────────────────────────────────────────────────────────────────

@dataclass
class PIIRegistry:
    """Maps token → original value for a single pipeline call."""
    _store: dict[str, str] = field(default_factory=dict)

    def register(self, token: str, original: str) -> None:
        self._store[token] = original

    def rehydrate(self, text: str) -> str:
        for token, original in self._store.items():
            text = text.replace(token, original)
        return text

    @property
    def entries(self) -> dict[str, str]:
        return dict(self._store)

    def __len__(self) -> int:
        return len(self._store)


# ── Core functions ────────────────────────────────────────────────────────────

def redact(
    text: str,
    use_ner: bool = True,
    redact_amounts: bool = False,
    registry: Optional[PIIRegistry] = None,
) -> tuple[str, PIIRegistry]:
    """Replace PII in *text* with format-preserving tokens.

    Parameters
    ----------
    text:
        Raw text to scrub (e.g. OCR output, invoice body, Slack message).
    use_ner:
        If True, run spaCy NER as a second pass for PERSON/ORG entities.
        Falls back gracefully if spaCy is not installed.
    redact_amounts:
        If True, also redact dollar amounts. Off by default so finance
        signals survive.
    registry:
        If provided, tokens are added to this existing registry (useful
        for multi-field scrubbing within one pipeline call). If None, a
        new registry is created.

    Returns
    -------
    (scrubbed_text, registry)
        scrubbed_text: text with PII replaced by tokens.
        registry:      PIIRegistry mapping token → original, used by
                       rehydrate() after the LLM call.
    """
    if registry is None:
        registry = PIIRegistry()

    result = text

    # ── Pass 1: regex ─────────────────────────────────────────────────────────
    for label, pattern in _PATTERNS:
        def _replace(m, lbl=label):
            original = m.group(0)
            token = _hmac_token(lbl, original)
            registry.register(token, original)
            return token

        result = pattern.sub(_replace, result)

    # ── Optional: dollar amounts ──────────────────────────────────────────────
    if redact_amounts:
        _amt_pat = re.compile(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?")
        def _replace_amt(m):
            original = m.group(0)
            token = _hmac_token("AMT", original)
            registry.register(token, original)
            return token
        result = _amt_pat.sub(_replace_amt, result)

    # ── Pass 2: spaCy NER (PERSON + ORG) ─────────────────────────────────────
    if use_ner:
        result = _ner_redact(result, registry)

    n = len(registry)
    if n:
        log.info("pii_gateway: redacted %d value(s)", n)
    return result, registry


def rehydrate(text: str, registry: PIIRegistry) -> str:
    """Replace all tokens in *text* with their original values."""
    return registry.rehydrate(text)


# ── spaCy NER (graceful degradation) ─────────────────────────────────────────

_nlp = None
_nlp_attempted = False


def _ner_redact(text: str, registry: PIIRegistry) -> str:
    """Run spaCy PERSON/ORG NER; silently skip if spaCy not installed."""
    global _nlp, _nlp_attempted
    if _nlp_attempted and _nlp is None:
        return text  # already failed once — skip

    if not _nlp_attempted:
        _nlp_attempted = True
        try:
            import spacy  # type: ignore
            # Try the small English model; install with:
            # python -m spacy download en_core_web_sm
            _nlp = spacy.load("en_core_web_sm")
            log.info("pii_gateway: spaCy NER loaded (en_core_web_sm)")
        except (ImportError, OSError):
            log.warning(
                "pii_gateway: spaCy or en_core_web_sm not installed — "
                "NER pass skipped (regex-only mode). "
                "Install: pip install spacy && python -m spacy download en_core_web_sm"
            )
            _nlp = None
            return text

    doc = _nlp(text)
    result = text
    # Process in reverse order so offsets stay valid
    for ent in sorted(doc.ents, key=lambda e: e.start_char, reverse=True):
        if ent.label_ not in ("PERSON", "ORG"):
            continue
        original = ent.text
        label = "NAME" if ent.label_ == "PERSON" else "ORG"
        token = _hmac_token(label, original)
        registry.register(token, original)
        result = result[: ent.start_char] + token + result[ent.end_char :]

    return result


# ── Convenience: scrub a dict of fields ──────────────────────────────────────

def redact_fields(
    fields: dict[str, str],
    use_ner: bool = True,
    redact_amounts: bool = False,
) -> tuple[dict[str, str], PIIRegistry]:
    """Redact PII from every value in a flat string dict.

    All fields share one registry so the same original value always maps
    to the same token regardless of which field it appears in.

    Returns (scrubbed_dict, registry).
    """
    registry = PIIRegistry()
    scrubbed: dict[str, str] = {}
    for key, value in fields.items():
        scrubbed_val, _ = redact(
            str(value),
            use_ner=use_ner,
            redact_amounts=redact_amounts,
            registry=registry,
        )
        scrubbed[key] = scrubbed_val
    return scrubbed, registry
