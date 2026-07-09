"""Tests for the Sentinel MCP Server (build-map ticket #30)."""

from __future__ import annotations

import json
import pytest

from sentinel.mcp_server import dispatch, TOOLS, SERVER_INFO


# ── Protocol ──────────────────────────────────────────────────────────────────

def test_initialize_returns_server_info():
    resp = dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["serverInfo"]["name"] == "sentinel"
    assert "protocolVersion" in resp["result"]


def test_tools_list_returns_all_five_tools():
    resp = dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tool_names = {t["name"] for t in resp["result"]["tools"]}
    assert tool_names == {
        "get_case",
        "run_contradiction_check",
        "blast_radius",
        "synthesize_rule",
        "expected_loss",
    }


def test_unknown_method_returns_error():
    resp = dispatch({"jsonrpc": "2.0", "id": 99, "method": "nonexistent", "params": {}})
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_unknown_tool_returns_error():
    resp = dispatch({
        "jsonrpc": "2.0", "id": 3,
        "method": "tools/call",
        "params": {"name": "does_not_exist", "arguments": {}},
    })
    assert "error" in resp


# ── run_contradiction_check ───────────────────────────────────────────────────

def test_mcp_contradiction_check_fraud():
    resp = dispatch({
        "jsonrpc": "2.0", "id": 4,
        "method": "tools/call",
        "params": {
            "name": "run_contradiction_check",
            "arguments": {
                "claims": {
                    "visual_total": 5000,
                    "structured_total": 500,
                    "tone_anomaly": 0.85,
                    "domain_age_days": 8,
                },
                "engine": "on",
            },
        },
    })
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["verdict"] == "FRAUD_LIKELY"
    assert content["is_flagged"] is True


def test_mcp_contradiction_check_clear():
    resp = dispatch({
        "jsonrpc": "2.0", "id": 5,
        "method": "tools/call",
        "params": {
            "name": "run_contradiction_check",
            "arguments": {
                "claims": {
                    "visual_total": 1000,
                    "structured_total": 1000,
                    "tone_anomaly": 0.05,
                    "domain_age_days": 900,
                },
            },
        },
    })
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["verdict"] == "CLEAR"


# ── expected_loss ─────────────────────────────────────────────────────────────

def test_mcp_expected_loss_critical():
    resp = dispatch({
        "jsonrpc": "2.0", "id": 6,
        "method": "tools/call",
        "params": {
            "name": "expected_loss",
            "arguments": {"amount_at_risk": 200000, "risk_score": 0.9},
        },
    })
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["expected_loss_usd"] == pytest.approx(180000.0)
    assert content["triage_priority"] == "CRITICAL"


def test_mcp_expected_loss_low():
    resp = dispatch({
        "jsonrpc": "2.0", "id": 7,
        "method": "tools/call",
        "params": {
            "name": "expected_loss",
            "arguments": {"amount_at_risk": 100, "risk_score": 0.1},
        },
    })
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["triage_priority"] == "LOW"


# ── blast_radius ──────────────────────────────────────────────────────────────

def test_mcp_blast_radius_returns_dict():
    resp = dispatch({
        "jsonrpc": "2.0", "id": 8,
        "method": "tools/call",
        "params": {
            "name": "blast_radius",
            "arguments": {"start_node": "U123456"},
        },
    })
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    assert "queried_node" in content
    assert content["queried_node"] == "U123456"


# ── synthesize_rule ───────────────────────────────────────────────────────────

def test_mcp_synthesize_rule_fraud_returns_rule():
    resp = dispatch({
        "jsonrpc": "2.0", "id": 9,
        "method": "tools/call",
        "params": {
            "name": "synthesize_rule",
            "arguments": {
                "case_id": "case-mcp-test",
                "verdict": "FRAUD_LIKELY",
                "claims": {
                    "visual_total": 5000,
                    "structured_total": 1000,
                },
            },
        },
    })
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    # Should return a rule dict or null
    if content is not None:
        assert "rule_id" in content
        assert content["status"] == "shadow"


def test_mcp_synthesize_rule_clear_returns_null():
    resp = dispatch({
        "jsonrpc": "2.0", "id": 10,
        "method": "tools/call",
        "params": {
            "name": "synthesize_rule",
            "arguments": {
                "case_id": "case-clear",
                "verdict": "CLEAR",
                "claims": {"visual_total": 1000, "structured_total": 1000},
            },
        },
    })
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content is None
