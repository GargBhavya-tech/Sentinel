"""Tests for the BFS blast-radius mapper (build-map ticket #19)."""

from __future__ import annotations

import pytest

from sentinel.graph.cache import get_graph, _lock
from sentinel.graph.blast_radius import blast_radius, blast_radius_sync


def setup_function():
    """Clear the graph before each test."""
    G = get_graph()
    G.clear()


@pytest.mark.asyncio
async def test_blast_radius_single_node():
    G = get_graph()
    G.add_node("U1", node_type="user", display_name="User 1")

    res = await blast_radius("U1", depth=1)
    
    assert res.start_node == "U1"
    assert res.depth == 1
    assert res.total_reached == 0  # Only itself in graph, reaching nothing else
    assert res.user_count == 0
    assert len(res.nodes) == 1
    assert len(res.edges) == 0


@pytest.mark.asyncio
async def test_blast_radius_bfs_propagation():
    G = get_graph()
    # Path: U1 -> C1 -> U2 -> F1
    G.add_node("U1", node_type="user")
    G.add_node("C1", node_type="channel")
    G.add_node("U2", node_type="user")
    G.add_node("F1", node_type="file")

    G.add_edge("U1", "C1", edge_type="posted_in")
    G.add_edge("U2", "C1", edge_type="posted_in")
    G.add_edge("U2", "F1", edge_type="uploaded")

    # Depth 1: U1 reaches C1
    res1 = await blast_radius("U1", depth=1)
    assert res1.total_reached == 1
    assert res1.channel_count == 1
    assert res1.reached_channels[0].node_id == "C1"

    # Depth 2: U1 reaches C1, U2
    res2 = await blast_radius("U1", depth=2)
    assert res2.total_reached == 2
    assert res2.channel_count == 1
    assert res2.user_count == 1

    # Depth 3: U1 reaches C1, U2, F1
    res3 = await blast_radius("U1", depth=3)
    assert res3.total_reached == 3
    assert res3.channel_count == 1
    assert res3.user_count == 1
    assert res3.file_count == 1


@pytest.mark.asyncio
async def test_blast_radius_dict_format():
    G = get_graph()
    G.add_node("U1", node_type="user", display_name="User 1")
    G.add_node("C1", node_type="channel", name="general")
    G.add_edge("U1", "C1", edge_type="posted_in")

    res = await blast_radius("U1", depth=1)
    d = res.to_dict()

    assert d["start_node"] == "U1"
    assert d["total_reached"] == 1
    assert len(d["reached_channels"]) == 1
    assert d["reached_channels"][0]["node_id"] == "C1"
    assert "elapsed_ms" in d


def test_blast_radius_sync_wrapper():
    """Ensure the sync wrapper works properly."""
    G = get_graph()
    G.add_node("U1", node_type="user")
    
    res = blast_radius_sync("U1", depth=1)
    assert res.start_node == "U1"
