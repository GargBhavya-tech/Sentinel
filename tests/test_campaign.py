"""Tests for Campaign Clustering (build-map ticket #23)."""

from __future__ import annotations

from sentinel.graph.cache import get_graph
from sentinel.graph.campaign import build_campaign_summary


def setup_function():
    get_graph().clear()


def test_build_campaign_summary_empty():
    summary = build_campaign_summary()
    assert summary.total_clusters == 0
    assert summary.singleton_count == 0
    
    blocks = summary.to_slack_blocks()
    assert len(blocks) == 2
    assert "no multi-node campaign clusters" in blocks[1]["text"]["text"].lower()


def test_build_campaign_summary_with_clusters():
    G = get_graph()
    
    # Cluster 1: U1, C1, U2
    G.add_node("U1", node_type="user", registrar="GoDaddy")
    G.add_node("C1", node_type="channel")
    G.add_node("U2", node_type="user", registrar="GoDaddy")
    G.add_edge("U1", "C1")
    G.add_edge("U2", "C1")

    # Cluster 2: F1, C2
    G.add_node("F1", node_type="file")
    G.add_node("C2", node_type="channel")
    G.add_edge("F1", "C2")

    # Singleton: U3
    G.add_node("U3", node_type="user")

    summary = build_campaign_summary(min_cluster_size=2)
    
    assert summary.total_clusters == 2
    assert summary.singleton_count == 1
    
    # Clusters should be sorted by size descending (Cluster 1 has 3, Cluster 2 has 2)
    assert summary.clusters[0].size == 3
    assert summary.clusters[0].shared_registrar == "GoDaddy"
    assert len(summary.clusters[0].user_nodes) == 2
    
    assert summary.clusters[1].size == 2
    assert len(summary.clusters[1].file_nodes) == 1
    
    # Check Slack blocks
    blocks = summary.to_slack_blocks()
    assert any("Cluster 1" in str(b) for b in blocks)
    assert any("Cluster 2" in str(b) for b in blocks)
    assert any("1 isolated node(s)" in str(b) for b in blocks)
