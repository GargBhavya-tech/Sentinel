"""Tests for the graph cache (build-map ticket #3).

These tests run entirely in-process (no Slack, no DB, no network).
They verify the graph cache correctly ingests events and returns
accurate BFS neighbors.
"""

import asyncio
import pytest

# Reset the graph between tests by re-importing and patching the module
from sentinel.graph import cache as _cache_mod


@pytest.fixture(autouse=True)
def reset_graph():
    """Clear the graph before each test."""
    import networkx as nx
    _cache_mod._graph = nx.DiGraph()


@pytest.mark.asyncio
async def test_message_event_creates_user_channel_edge():
    event = {
        "type": "message",
        "user": "U111",
        "channel": "C001",
        "ts": "1700000001.000001",
    }
    await _cache_mod.ingest_event(event)

    G = _cache_mod.get_graph()
    assert G.has_node("U111")
    assert G.has_node("C001")
    assert G.has_edge("U111", "C001")
    assert G["U111"]["C001"]["edge_type"] == "posted_in"


@pytest.mark.asyncio
async def test_repeated_messages_increment_count():
    for ts in ("1700000001.0", "1700000002.0", "1700000003.0"):
        await _cache_mod.ingest_event({"type": "message", "user": "U111", "channel": "C001", "ts": ts})

    G = _cache_mod.get_graph()
    assert G["U111"]["C001"]["count"] == 3


@pytest.mark.asyncio
async def test_file_shared_creates_three_node_chain():
    event = {
        "type": "file_shared",
        "user_id": "U222",
        "file_id": "F999",
        "channel_id": "C002",
        "file": {"name": "invoice.pdf", "mimetype": "application/pdf"},
        "ts": "1700000010.0",
    }
    await _cache_mod.ingest_event(event)

    G = _cache_mod.get_graph()
    assert G.has_edge("U222", "F999")
    assert G.has_edge("F999", "C002")
    assert G.nodes["F999"]["name"] == "invoice.pdf"


@pytest.mark.asyncio
async def test_neighbors_bfs_depth_1():
    # U111 → C001 ← U222
    await _cache_mod.ingest_event({"type": "message", "user": "U111", "channel": "C001", "ts": "1.0"})
    await _cache_mod.ingest_event({"type": "message", "user": "U222", "channel": "C001", "ts": "2.0"})

    # From U111 at depth 1 we should reach C001 (direct neighbour)
    result = await _cache_mod.neighbors("U111", depth=1)
    assert "C001" in result
    assert "U222" not in result  # U222 is 2 hops away


@pytest.mark.asyncio
async def test_neighbors_bfs_depth_2():
    await _cache_mod.ingest_event({"type": "message", "user": "U111", "channel": "C001", "ts": "1.0"})
    await _cache_mod.ingest_event({"type": "message", "user": "U222", "channel": "C001", "ts": "2.0"})

    result = await _cache_mod.neighbors("U111", depth=2)
    # At depth 2: U111→C001→U222
    assert "C001" in result
    assert "U222" in result


@pytest.mark.asyncio
async def test_neighbors_unknown_node_returns_empty():
    result = await _cache_mod.neighbors("U_DOES_NOT_EXIST", depth=3)
    assert result == set()


@pytest.mark.asyncio
async def test_graph_snapshot_structure():
    await _cache_mod.ingest_event({"type": "message", "user": "U111", "channel": "C001", "ts": "1.0"})
    snap = _cache_mod.get_graph_snapshot()

    assert snap["node_count"] == 2
    assert snap["edge_count"] == 1
    assert any(n["id"] == "U111" for n in snap["nodes"])
    assert any(e["source"] == "U111" and e["target"] == "C001" for e in snap["edges"])
