"""Tests for Graph Analytics (build-map ticket #20)."""

from __future__ import annotations

from sentinel.graph.cache import get_graph
from sentinel.graph.analytics import (
    compute_pagerank,
    find_campaign_clusters,
    analyze_blast_radius,
    top_spreaders,
)


def setup_function():
    get_graph().clear()


def test_compute_pagerank_empty():
    assert compute_pagerank() == {}


def test_compute_pagerank():
    G = get_graph()
    # Hub topology
    G.add_node("U1", node_type="user")
    for i in range(5):
        G.add_node(f"C{i}", node_type="channel")
        G.add_edge("U1", f"C{i}", count=1)
        
    pr = compute_pagerank()
    assert "U1" in pr
    # U1 should have the highest score as the hub
    assert pr["U1"] > pr["C0"]


def test_find_campaign_clusters():
    G = get_graph()
    G.add_edge("U1", "C1")
    G.add_edge("U2", "C2")
    
    clusters = find_campaign_clusters()
    assert len(clusters) == 2
    
    G.add_edge("U1", "C2")
    clusters = find_campaign_clusters()
    assert len(clusters) == 1  # Now connected


def test_analyze_blast_radius():
    G = get_graph()
    G.add_node("U1", node_type="user")
    G.add_edge("U1", "C1")
    
    res = analyze_blast_radius()
    assert res["super_spreader"] == "U1"
    assert res["total_campaign_clusters"] == 1
    assert len(res["clusters"]) == 1


def test_top_spreaders():
    G = get_graph()
    G.add_node("U1", node_type="user")
    G.add_node("U2", node_type="user")
    G.add_node("C1", node_type="channel")
    
    G.add_edge("U1", "C1", count=10)
    G.add_edge("U2", "C1", count=1)
    
    spreaders = top_spreaders(n=2)
    assert len(spreaders) == 2
    assert spreaders[0][0] == "U1"  # U1 is the main spreader
    assert spreaders[1][0] == "U2"
