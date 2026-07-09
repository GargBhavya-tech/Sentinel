"""In-memory workspace graph cache (build-map ticket #3).

Architecture
------------
A module-level `nx.DiGraph` is the substrate for:
  - BFS Blast-Radius Mapper (#19)   — finds every node reachable from a threat
  - Graph Analytics (#20)           — PageRank centrality, connected components

Node types
----------
  user      — Slack user ID (U0123456789)  → attrs: display_name, first_seen
  channel   — Slack channel ID (C0123456789) → attrs: name, first_seen
  file      — Slack file ID (F0123456789)  → attrs: name, mimetype, first_seen

Edge types (directed)
---------------------
  user → channel   posted_in   (weight = message count, edge attrs: latest_ts)
  user → file      uploaded    (edge attrs: ts)
  file → channel   shared_in   (edge attrs: ts)

Thread safety
-------------
Slack events arrive on the asyncio event loop. The graph is protected by an
`asyncio.Lock` so concurrent ingestion is safe. BFS/read operations also hold
the lock momentarily.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

import networkx as nx  # type: ignore

log = logging.getLogger(__name__)

# ── Module-level singletons ────────────────────────────────────────────────────
_graph: nx.DiGraph = nx.DiGraph()
_lock: asyncio.Lock = asyncio.Lock()


def get_graph() -> nx.DiGraph:
    """Return the raw NetworkX graph (use carefully — not thread-safe alone)."""
    return _graph


# ── Node helpers ───────────────────────────────────────────────────────────────

def _ensure_node(G: nx.DiGraph, node_id: str, node_type: str, **attrs) -> None:
    """Add node if absent; merge attrs if present."""
    if not G.has_node(node_id):
        G.add_node(node_id, node_type=node_type, **attrs)
    else:
        G.nodes[node_id].update(attrs)


# ── Public API ─────────────────────────────────────────────────────────────────

async def ingest_event(event: dict[str, Any]) -> None:
    """Add a Slack event to the graph.

    Handles three event shapes:
      - message / app_mention  → user → channel edge
      - file_shared            → user → file, file → channel edges
      - member_joined_channel  → user → channel edge (lighter weight)
    """
    event_type = event.get("type", "")
    ts = event.get("ts") or event.get("event_ts", "0")

    async with _lock:
        if event_type in ("message", "app_mention"):
            uid = event.get("user")
            cid = event.get("channel")
            if not uid or not cid:
                return

            _ensure_node(_graph, uid, "user")
            _ensure_node(_graph, cid, "channel")

            if _graph.has_edge(uid, cid):
                _graph[uid][cid]["count"] = _graph[uid][cid].get("count", 0) + 1
                _graph[uid][cid]["latest_ts"] = ts
            else:
                _graph.add_edge(uid, cid, edge_type="posted_in", count=1, latest_ts=ts)

            log.debug("graph: %s → %s (posted_in)", uid, cid)

        elif event_type == "file_shared":
            uid = event.get("user_id")
            fid = event.get("file_id")
            cid = event.get("channel_id")
            if not (uid and fid):
                return

            fname = event.get("file", {}).get("name", "")
            mime = event.get("file", {}).get("mimetype", "")

            _ensure_node(_graph, uid, "user")
            _ensure_node(_graph, fid, "file", name=fname, mimetype=mime)

            _graph.add_edge(uid, fid, edge_type="uploaded", ts=ts)

            if cid:
                _ensure_node(_graph, cid, "channel")
                _graph.add_edge(fid, cid, edge_type="shared_in", ts=ts)

            log.debug("graph: %s → %s → %s (file_shared)", uid, fid, cid)

        elif event_type == "member_joined_channel":
            uid = event.get("user")
            cid = event.get("channel")
            if uid and cid:
                _ensure_node(_graph, uid, "user")
                _ensure_node(_graph, cid, "channel")
                if not _graph.has_edge(uid, cid):
                    _graph.add_edge(uid, cid, edge_type="member_of", count=0, latest_ts=ts)


async def neighbors(node_id: str, depth: int = 2) -> set[str]:
    """BFS from node_id up to `depth` hops over the undirected view.

    Returns the set of reachable node IDs (excluding the start node itself).
    Used by the Blast-Radius Mapper (#19): call this on a flagged
    user/file/channel to find every connected node.
    """
    async with _lock:
        if not _graph.has_node(node_id):
            return set()

        # Work on an undirected view so we propagate in both directions
        undirected = _graph.to_undirected(as_view=True)

        visited: set[str] = {node_id}
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue
            for nb in undirected.neighbors(current):
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, d + 1))

        visited.discard(node_id)
        return visited


def get_graph_snapshot() -> dict[str, Any]:
    """Return a JSON-serialisable snapshot of the current graph.

    Used by the React console's force-directed graph panel. Nodes carry their
    type and attrs; edges carry type and weight.
    """
    nodes = [
        {"id": n, **data}
        for n, data in _graph.nodes(data=True)
    ]
    edges = [
        {"source": u, "target": v, **data}
        for u, v, data in _graph.edges(data=True)
    ]
    return {
        "node_count": _graph.number_of_nodes(),
        "edge_count": _graph.number_of_edges(),
        "nodes": nodes,
        "edges": edges,
    }
