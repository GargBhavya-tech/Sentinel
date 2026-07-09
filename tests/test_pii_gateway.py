"""Tests for the PII Redaction Gateway (#4).

All tests run in-process with no Slack, no DB, no network.
The pepper env var is set in conftest.py (via os.environ.setdefault).
"""

import pytest
from sentinel.pii_gateway import (
    PIIRegistry,
    redact,
    redact_fields,
    rehydrate,
    _hmac_token,
)


# ── Token format ──────────────────────────────────────────────────────────────

def test_token_uses_unicode_brackets():
    token = _hmac_token("TEST", "hello")
    assert token.startswith("\u27e6TEST:")
    assert token.endswith("\u27e7")


def test_same_value_always_same_token():
    t1 = _hmac_token("EMAIL", "alice@example.com")
    t2 = _hmac_token("EMAIL", "alice@example.com")
    assert t1 == t2


def test_different_values_different_tokens():
    t1 = _hmac_token("EMAIL", "alice@example.com")
    t2 = _hmac_token("EMAIL", "bob@example.com")
    assert t1 != t2


# ── SSN ───────────────────────────────────────────────────────────────────────

def test_ssn_redacted():
    text = "Customer SSN is 123-45-6789 per the application."
    scrubbed, reg = redact(text, use_ner=False)
    assert "123-45-6789" not in scrubbed
    assert len(reg) >= 1


def test_ssn_rehydrated():
    text = "SSN: 987-65-4321"
    scrubbed, reg = redact(text, use_ner=False)
    restored = rehydrate(scrubbed, reg)
    assert "987-65-4321" in restored


# ── Email ─────────────────────────────────────────────────────────────────────

def test_email_redacted():
    text = "Please contact finance@acmecorp.com for payment queries."
    scrubbed, reg = redact(text, use_ner=False)
    assert "finance@acmecorp.com" not in scrubbed
    assert "\u27e6EMAIL:" in scrubbed


def test_email_rehydrated():
    text = "Send to user@example.com immediately."
    scrubbed, reg = redact(text, use_ner=False)
    assert "user@example.com" not in scrubbed
    assert "user@example.com" in rehydrate(scrubbed, reg)


# ── Phone ─────────────────────────────────────────────────────────────────────

def test_phone_redacted():
    text = "Call us at +1-800-555-0199 for support."
    scrubbed, reg = redact(text, use_ner=False)
    assert "800-555-0199" not in scrubbed


# ── Format preservation (stylometric signal survives) ────────────────────────

def test_surrounding_text_intact():
    """Text around the PII must be unchanged — stylometric signals survive."""
    text = "Dear sir, your SSN 123-45-6789 has been verified. Regards."
    scrubbed, _ = redact(text, use_ner=False)
    assert "Dear sir," in scrubbed
    assert "has been verified" in scrubbed
    assert "Regards" in scrubbed


def test_amount_not_redacted_by_default():
    """Dollar amounts should NOT be redacted unless caller opts in."""
    text = "Invoice total: $12,500.00"
    scrubbed, _ = redact(text, use_ner=False, redact_amounts=False)
    assert "$12,500.00" in scrubbed


def test_amount_redacted_when_opted_in():
    text = "Invoice total: $12,500.00"
    scrubbed, _ = redact(text, use_ner=False, redact_amounts=True)
    assert "$12,500.00" not in scrubbed


# ── redact_fields ─────────────────────────────────────────────────────────────

def test_redact_fields_shares_registry():
    """Same value appearing in two fields maps to the same token."""
    fields = {
        "body": "Contact: user@x.com",
        "footer": "Reply to user@x.com",
    }
    scrubbed, reg = redact_fields(fields, use_ner=False)
    # The same email token appears in both fields
    tokens = [t for t in reg.entries if t.startswith("\u27e6EMAIL:")]
    assert len(tokens) == 1     # de-duplicated — one entry in the registry


def test_redact_fields_all_fields_scrubbed():
    fields = {
        "name_field": "John Doe",     # NER — skipped in no-ner mode
        "ssn_field": "123-45-6789",
        "email_field": "jd@test.com",
    }
    scrubbed, reg = redact_fields(fields, use_ner=False)
    assert "123-45-6789" not in scrubbed["ssn_field"]
    assert "jd@test.com" not in scrubbed["email_field"]


# ── Missing pepper ────────────────────────────────────────────────────────────

def test_missing_pepper_raises():
    import os
    original = os.environ.pop("PII_HMAC_PEPPER", None)
    try:
        with pytest.raises(RuntimeError, match="PII_HMAC_PEPPER"):
            _hmac_token("TEST", "value")
    finally:
        if original is not None:
            os.environ["PII_HMAC_PEPPER"] = original
