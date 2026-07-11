"""BFS Blast-Radius Mapper — build-map ticket #19.

On a confirmed threat, runs BFS over the local graph cache (#3) to find
every user/channel/thread the pattern touched.

Build-map spec: "Render it in-thread as a graph. 'This template touched 3
other channels in 14 days.' Done when: a seeded pattern shows a correct
multi-channel reach graph, computed locally in <1s."

Architecture
------------
- `blast_radius(start_node, depth)` is the main entry point.
- It calls `cache.neighbors()` (BFS already implemented in cache.py) and
  then enriches the result with node-type breakdown and graph analytics.
- Returns a `BlastRadiusResult` dataclass that is JSON-serialisable and
  directly consumable by the MCP `blast_radius` tool and the React console.

Timing guarantee: BFS over an in-memory NetworkX graph with thousands of
nodes runs in microseconds, well under the <1s requirement.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .cache import get_graph, neighbors as _bfs_neighbors
from .analytics import analyze_blast_radius, top_spreaders

log = logging.getLogger(__name__)


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class ReachedNode:
    node_id: str
    node_type: str          # "user" | "channel" | "file" | "unknown"
    display_name: str       # best available label
    edge_count: int = 0     # number of edges touching this node in the subgraph


@dataclass
class BlastRadiusResult:
    start_node: str
    depth: int
    elapsed_ms: float

    # Breakdown by type
    reached_users: list[ReachedNode] = field(default_factory=list)
    reached_channels: list[ReachedNode] = field(default_factory=list)
    reached_files: list[ReachedNode] = field(default_factory=list)

    # Totals
    total_reached: int = 0
    channel_count: int = 0
    user_count: int = 0
    file_count: int = 0

    # Graph analytics
    super_spreader: Optional[str] = None
    super_spreader_score: float = 0.0
    campaign_cluster_count: int = 0

    # For the force-directed graph panel
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)

    # Human-readable summary (for Slack thread card)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "start_node": self.start_node,
            "depth": self.depth,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "total_reached": self.total_reached,
            "user_count": self.user_count,
            "channel_count": self.channel_count,
            "file_count": self.file_count,
            "super_spreader": self.super_spreader,
            "super_spreader_score": self.super_spreader_score,
            "campaign_cluster_count": self.campaign_cluster_count,
            "summary": self.summary,
            "reached_users": [
                {"node_id": n.node_id, "display_name": n.display_name, "edge_count": n.edge_count}
                for n in self.reached_users
            ],
            "reached_channels": [
                {"node_id": n.node_id, "display_name": n.display_name, "edge_count": n.edge_count}
                for n in self.reached_channels
            ],
            "reached_files": [
                {"node_id": n.node_id, "display_name": n.display_name, "edge_count": n.edge_count}
                for n in self.reached_files
            ],
            "nodes": self.nodes,
            "edges": self.edges,
        }


# ── Main entry point ───────────────────────────────────────────────────────────

async def blast_radius(
    start_node: str,
    depth: int = 3,
) -> BlastRadiusResult:
    """Run BFS blast-radius analysis from a node.

    Parameters
    ----------
    start_node : str
        Slack user ID (U…), channel ID (C…), or file ID (F…) to
        start BFS propagation from.
    depth : int
        How many hops to follow. Default 3 (user → channel → user → …).

    Returns
    -------
    BlastRadiusResult
        Fully populated result with node breakdown, analytics, and the
        subgraph for the force-directed visualisation.
    """
    t0 = time.perf_counter()

    # ── BFS ───────────────────────────────────────────────────────────────────
    reached: set[str] = await _bfs_neighbors(start_node, depth=depth)

    G = get_graph()

    # ── Build subgraph for visualisation ─────────────────────────────────────
    all_nodes = reached | {start_node}
    subgraph = G.subgraph(all_nodes)

    nodes_payload: list[dict] = []
    for nid in all_nodes:
        attrs = G.nodes.get(nid, {})
        nodes_payload.append({
            "id": nid,
            "node_type": attrs.get("node_type", "unknown"),
            "label": attrs.get("display_name") or attrs.get("name") or nid,
            "is_origin": nid == start_node,
        })

    edges_payload: list[dict] = [
        {
            "source": u,
            "target": v,
            "edge_type": data.get("edge_type", ""),
            "count": data.get("count", 1),
        }
        for u, v, data in subgraph.edges(data=True)
    ]

    # ── Node breakdown ────────────────────────────────────────────────────────
    users: list[ReachedNode] = []
    channels: list[ReachedNode] = []
    files: list[ReachedNode] = []

    for nid in reached:
        attrs = G.nodes.get(nid, {})
        ntype = attrs.get("node_type", "unknown")
        label = attrs.get("display_name") or attrs.get("name") or nid
        edge_count = subgraph.degree(nid) if subgraph.has_node(nid) else 0
        node = ReachedNode(node_id=nid, node_type=ntype, display_name=label, edge_count=edge_count)

        if ntype == "user":
            users.append(node)
        elif ntype == "channel":
            channels.append(node)
        elif ntype == "file":
            files.append(node)

    # Sort by edge count descending (most connected first)
    users.sort(key=lambda n: -n.edge_count)
    channels.sort(key=lambda n: -n.edge_count)

    # ── Graph analytics over reached subgraph ─────────────────────────────────
    analytics = analyze_blast_radius(list(all_nodes) if all_nodes else None)
    spreaders = top_spreaders(list(all_nodes), n=1)
    super_spreader = spreaders[0][0] if spreaders else analytics.get("super_spreader")
    super_spreader_score = spreaders[0][1] if spreaders else analytics.get("super_spreader_score", 0.0)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # ── Human-readable summary ────────────────────────────────────────────────
    parts = []
    if channels:
        ch_names = ", ".join(
            f"#{n.display_name}" if not n.display_name.startswith("#") else n.display_name
            for n in channels[:3]
        )
        suffix = f" and {len(channels) - 3} more" if len(channels) > 3 else ""
        parts.append(f"touched {len(channels)} channel(s): {ch_names}{suffix}")
    if users:
        parts.append(f"reached {len(users)} user(s)")
    if files:
        parts.append(f"shared {len(files)} file(s)")

    if super_spreader:
        parts.append(f"propagation hub: {super_spreader} (score {super_spreader_score:.2f})")

    summary = (
        f"Blast radius from {start_node} (depth={depth}): "
        + ("; ".join(parts) if parts else "no connected nodes found")
        + f" — computed in {elapsed_ms:.1f}ms"
    )

    log.info("blast_radius: %s", summary)

    return BlastRadiusResult(
        start_node=start_node,
        depth=depth,
        elapsed_ms=elapsed_ms,
        reached_users=users,
        reached_channels=channels,
        reached_files=files,
        total_reached=len(reached),
        channel_count=len(channels),
        user_count=len(users),
        file_count=len(files),
        super_spreader=super_spreader,
        super_spreader_score=super_spreader_score,
        campaign_cluster_count=analytics.get("total_campaign_clusters", 0),
        nodes=nodes_payload,
        edges=edges_payload,
        summary=summary,
    )


# ── Sync wrapper (for MCP / non-async callers) ────────────────────────────────

def blast_radius_sync(start_node: str, depth: int = 3) -> BlastRadiusResult:
    """Run blast_radius() synchronously (creates a new event loop if needed)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an existing event loop — schedule as a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    lambda: asyncio.run(blast_radius(start_node, depth))
                )
                return future.result()
        return loop.run_until_complete(blast_radius(start_node, depth))
    except RuntimeError:
        return asyncio.run(blast_radius(start_node, depth))
