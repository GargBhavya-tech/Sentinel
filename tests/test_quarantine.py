"""Tests for Active Quarantine (build-map ticket #22)."""

from __future__ import annotations

import pytest

from sentinel.graph.cache import get_graph
from sentinel.graph.quarantine import (
    quarantine,
    lift_quarantine,
    is_quarantined,
    clear_log,
    get_quarantine_log,
)


def setup_function():
    clear_log()
    get_graph().clear()


def test_quarantine_single_node():
    G = get_graph()
    G.add_node("U1", node_type="user")

    res = quarantine("case-1", ["U1"], "Testing quarantine")
    
    assert res.total_new == 1
    assert len(res.already_quarantined) == 0
    assert is_quarantined("U1")
    
    log_entries = get_quarantine_log()
    assert len(log_entries) == 1
    assert log_entries[0]["node_id"] == "U1"
    assert log_entries[0]["reason"] == "Testing quarantine"
    assert "QUARANTINE" in log_entries[0]["audit_note"]


def test_quarantine_is_idempotent():
    G = get_graph()
    G.add_node("U1", node_type="user")

    # First quarantine
    res1 = quarantine("case-1", ["U1"], "First")
    assert res1.total_new == 1

    # Second quarantine — should be skipped
    res2 = quarantine("case-2", ["U1"], "Second")
    assert res2.total_new == 0
    assert res2.already_quarantined == ["U1"]


def test_quarantine_multiple_nodes():
    G = get_graph()
    G.add_node("U1", node_type="user")
    G.add_node("C1", node_type="channel")
    
    quarantine("case-1", ["U1"], "Existing")

    res = quarantine("case-1", ["U1", "C1", "F1"], "Bulk")
    # U1 is already quarantined. C1 and F1 (unknown type) are new.
    assert res.total_new == 2
    assert "U1" in res.already_quarantined


def test_lift_quarantine():
    G = get_graph()
    G.add_node("U1", node_type="user")

    quarantine("case-1", ["U1"], "Test")
    assert is_quarantined("U1")

    lifted = lift_quarantine("U1")
    assert lifted is True
    assert not is_quarantined("U1")

    # Double lift should return False
    assert lift_quarantine("U1") is False
