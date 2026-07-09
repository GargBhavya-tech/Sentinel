"""Tests for NLP Agent (#9)."""

import pytest
from sentinel.agents.nlp_agent import NLPResult, analyze


# ── Scam type classification ──────────────────────────────────────────────────

def test_bec_pattern_detected():
    text = (
        "This is a strictly confidential request from the CEO. "
        "Please wire transfer $87,000 to the new account details below. "
        "Do not discuss with anyone."
    )
    result = analyze(case_id="c1", text=text)
    assert result.scam_type == "BEC"
    assert result.scam_confidence > 0.0


def test_invoice_fraud_detected():
    text = (
        "FINAL NOTICE: Your account is past due. Immediate payment of $15,400 "
        "is required or we will refer this to our collection agency."
    )
    result = analyze(case_id="c2", text=text)
    assert result.scam_type == "INVOICE"


def test_phishing_detected():
    text = (
        "Your account will be suspended. Please verify your account by clicking "
        "the link below and confirm your details immediately."
    )
    result = analyze(case_id="c3", text=text)
    assert result.scam_type == "PHISHING"


def test_advance_fee_detected():
    text = (
        "Dear Beneficiary, you have been selected to receive an inheritance "
        "of $4.5 million dollars. A small administrative fee is required to release funds."
    )
    result = analyze(case_id="c4", text=text)
    assert result.scam_type == "ADVANCE_FEE"


def test_vishing_detected():
    text = (
        "Your social security number has been suspended due to suspicious activity. "
        "Press 1 to speak to an IRS agent or you will face arrest warrant."
    )
    result = analyze(case_id="c5", text=text)
    assert result.scam_type == "VISHING"


def test_romance_scam_detected():
    text = (
        "My darling, I am a military officer stationed abroad. I fell in love "
        "with you. Please send me money via Western Union to help with customs."
    )
    result = analyze(case_id="c6", text=text)
    assert result.scam_type == "ROMANCE"


def test_clean_invoice_unknown():
    text = (
        "Please find attached the invoice for consulting services provided in June. "
        "Total: $4,500. Payment due within 30 days. Thank you."
    )
    result = analyze(case_id="c7", text=text)
    # Should not confidently classify as any scam type
    assert result.scam_confidence < 0.25 or result.scam_type == "UNKNOWN"


# ── Urgency scoring ───────────────────────────────────────────────────────────

def test_high_urgency_bec():
    text = (
        "URGENT: wire transfer immediately. Do not delay. Do not tell anyone. "
        "Complete within the hour. This is time-sensitive."
    )
    result = analyze(case_id="c8", text=text)
    assert result.urgency >= 0.5


def test_low_urgency_normal_email():
    text = "Hi, please review the attached budget report when you have a moment."
    result = analyze(case_id="c9", text=text)
    assert result.urgency < 0.25


def test_urgency_capped_at_one():
    # Pile on every urgency phrase
    text = " ".join([
        "immediately", "urgent", "asap", "right now", "today only",
        "deadline", "last chance", "do not delay", "time-sensitive",
        "within the hour", "final notice", "do not tell anyone",
    ])
    result = analyze(case_id="c10", text=text)
    assert result.urgency <= 1.0


# ── Multilingual / code-switched ─────────────────────────────────────────────

def test_hinglish_urgency_detected():
    text = "Jaldi karo, abhi bhejo account mein transfer karo. Turant."
    result = analyze(case_id="c11", text=text)
    assert result.urgency > 0


# ── Matched keywords ─────────────────────────────────────────────────────────

def test_matched_keywords_populated():
    text = "Wire transfer required. CEO request. Confidential."
    result = analyze(case_id="c12", text=text)
    assert len(result.matched_keywords) > 0


def test_clean_text_no_keywords():
    text = "Please find the attached purchase order for your records."
    result = analyze(case_id="c13", text=text)
    # Should have no or very few matched keywords
    assert result.scam_confidence < 0.2


# ── Claims output ─────────────────────────────────────────────────────────────

def test_to_claims_returns_two_claims():
    result = analyze(case_id="c14", text="urgent wire transfer ceo request")
    claims = result.to_claims()
    fields = {c.field for c in claims}
    assert "scam_type_score" in fields
    assert "urgency_score" in fields


def test_to_claims_agent_is_nlp():
    result = analyze(case_id="c15", text="invoice attached")
    for c in result.to_claims():
        assert c.agent == "nlp"
