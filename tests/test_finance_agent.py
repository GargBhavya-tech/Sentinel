"""Tests for Finance Agent (#8)."""

import pytest

from sentinel.agents.finance_agent import (
    FinanceResult,
    analyze,
    clear_invoice_tracker,
    clear_vendor_history,
    update_vendor_history,
    _ewma,
    _parse_csv,
)


def setup_function():
    clear_vendor_history()
    clear_invoice_tracker()


# ── EWMA math ─────────────────────────────────────────────────────────────────

def test_ewma_single_value():
    assert _ewma([5000.0]) == 5000.0


def test_ewma_decays_toward_new_values():
    vals = [1000.0, 1000.0, 1000.0, 10000.0]
    result = _ewma(vals)
    assert 1000.0 < result < 10000.0


def test_ewma_stable_returns_same():
    vals = [5000.0] * 10
    assert abs(_ewma(vals) - 5000.0) < 1.0


# ── CSV parsing ───────────────────────────────────────────────────────────────

def test_parse_csv_extracts_amount():
    csv = "amount,vendor,date\n$12500.00,Acme Corp,2026-07-01"
    amount, vendor, _, _ = _parse_csv(csv)
    assert amount == 12500.0


def test_parse_csv_extracts_vendor():
    csv = "amount,vendor\n5000,WidgetCo"
    _, vendor, _, _ = _parse_csv(csv)
    assert vendor == "WidgetCo"


def test_parse_csv_handles_dollar_sign():
    csv = "amount,vendor\n$7,500.00,ACME"
    amount, _, _, _ = _parse_csv(csv)
    assert amount == 7500.0


# ── Risk factors ──────────────────────────────────────────────────────────────

def test_new_vendor_adds_mild_risk():
    result = analyze(
        case_id="c1",
        amount=3000.0,
        vendor="BrandNewVendor",
    )
    factor_names = [f.name for f in result.risk_factors]
    assert "new_vendor" in factor_names


def test_ewma_deviation_flags_abnormal_amount():
    update_vendor_history("Acme Corp", 5000.0)
    update_vendor_history("Acme Corp", 5200.0)
    result = analyze(
        case_id="c2",
        amount=50_000.0,    # 10× the history — way above threshold
        vendor="Acme Corp",
    )
    factor_names = [f.name for f in result.risk_factors]
    assert "ewma_deviation" in factor_names
    assert result.risk_score > 0.3


def test_normal_amount_no_deviation_flag():
    update_vendor_history("Trusted Corp", 4800.0)
    update_vendor_history("Trusted Corp", 5100.0)
    result = analyze(
        case_id="c3",
        amount=5000.0,
        vendor="Trusted Corp",
    )
    factor_names = [f.name for f in result.risk_factors]
    assert "ewma_deviation" not in factor_names


def test_round_amount_flagged():
    result = analyze(case_id="c4", amount=100_000.0, vendor="V")
    factor_names = [f.name for f in result.risk_factors]
    assert "round_amount" in factor_names


def test_small_round_amount_not_flagged():
    result = analyze(case_id="c5", amount=5_000.0, vendor="V")
    factor_names = [f.name for f in result.risk_factors]
    assert "round_amount" not in factor_names


def test_weekend_submission_flagged():
    result = analyze(
        case_id="c6",
        amount=1000.0,
        vendor="V",
        invoice_date="2026-07-12",   # Sunday
    )
    factor_names = [f.name for f in result.risk_factors]
    assert "weekend_submission" in factor_names


def test_weekday_submission_not_flagged():
    result = analyze(
        case_id="c7",
        amount=1000.0,
        vendor="V",
        invoice_date="2026-07-09",   # Wednesday
    )
    factor_names = [f.name for f in result.risk_factors]
    assert "weekend_submission" not in factor_names


def test_duplicate_invoice_flagged():
    analyze(case_id="c8a", amount=1000.0, vendor="V", invoice_number="INV-001")
    result = analyze(case_id="c8b", amount=1000.0, vendor="V", invoice_number="INV-001")
    factor_names = [f.name for f in result.risk_factors]
    assert "duplicate_invoice" in factor_names


# ── Risk score bounds ─────────────────────────────────────────────────────────

def test_risk_score_bounded():
    update_vendor_history("X", 100.0)
    result = analyze(
        case_id="c9",
        amount=999_999.0,
        vendor="X",
        invoice_date="2026-07-12",   # Sunday
        invoice_number="DUP-999",
    )
    assert 0.0 <= result.risk_score <= 1.0


def test_clean_invoice_low_risk():
    update_vendor_history("GoodVendor", 4500.0)
    update_vendor_history("GoodVendor", 4700.0)
    result = analyze(
        case_id="c10",
        amount=4_600.0,
        vendor="GoodVendor",
        invoice_date="2026-07-09",
        invoice_number="INV-UNIQUE-12345",
    )
    assert result.risk_score < 0.3


# ── Claims ─────────────────────────────────────────────────────────────────────

def test_to_claims_includes_structured_total():
    result = analyze(case_id="c11", amount=5000.0, vendor="V")
    claims = result.to_claims()
    assert any(c.field == "structured_total" for c in claims)
    assert any(c.field == "finance_risk" for c in claims)


def test_to_claims_agent_is_finance():
    result = analyze(case_id="c12", amount=1000.0, vendor="V")
    for c in result.to_claims():
        assert c.agent == "finance"


def test_pre_metrics_shortcut():
    result = analyze(
        case_id="c13",
        amount=999.0,
        vendor="V",
        pre_metrics={"structured_total": 12345.0, "finance_risk": 0.3},
    )
    assert result.structured_total == 12345.0
    assert result.risk_score == 0.3
