"""Graph Analytics module (build-map ticket #20).

Provides PageRank centrality to identify super-spreaders in the workspace
and connected-components to cluster campaigns on the local graph cache.
"""

from __future__ import annotations

import networkx as nx  # type: ignore
from typing import Any
import logging

from .cache import get_graph

log = logging.getLogger(__name__)


def compute_pagerank(
    nodes: list[str] | None = None, alpha: float = 0.85
) -> dict[str, float]:
    """Compute PageRank centrality on the workspace graph cache.

    Returns a dictionary of node_id -> pagerank_score.
    Used to name the 'super-spreader' account during an investigation.
    """
    G = get_graph()
    if nodes:
        G = G.subgraph(nodes)

    if G.number_of_nodes() == 0:
        return {}

    try:
        # PageRank is usually computed on a directed graph.
        pagerank_scores = nx.pagerank(G, alpha=alpha, weight="count")
        return pagerank_scores
    except Exception as e:
        log.error("Failed to compute PageRank: %s", e)
        return {}


def find_campaign_clusters(nodes: list[str] | None = None) -> list[set[str]]:
    """Find connected components in the graph cache to cluster campaigns.

    Returns a list of node sets, where each set represents a connected component.
    """
    G = get_graph()
    if nodes:
        G = G.subgraph(nodes)

    if G.number_of_nodes() == 0:
        return []

    try:
        # Connected components require an undirected graph
        undirected_G = G.to_undirected(as_view=True)
        clusters = list(nx.connected_components(undirected_G))
        return clusters
    except Exception as e:
        log.error("Failed to compute connected components: %s", e)
        return []


def analyze_blast_radius(start_nodes: list[str] | None = None) -> dict[str, Any]:
    """Analyze the graph from a set of starting nodes (e.g. flagged users/files).

    Runs PageRank to find the hub and returns campaign clusters.
    """
    scores = compute_pagerank(start_nodes)
    clusters = find_campaign_clusters(start_nodes)

    # Find the super-spreader (node with highest PageRank score that is a user)
    G = get_graph()
    if start_nodes:
        G = G.subgraph(start_nodes)
    super_spreader = None
    max_score = -1.0

    for node, score in scores.items():
        if G.nodes.get(node, {}).get("node_type") == "user" and score > max_score:
            max_score = score
            super_spreader = node

    # Count non-trivial clusters (size > 1)
    campaign_clusters = [c for c in clusters if len(c) > 1]

    result = {
        "super_spreader": super_spreader,
        "super_spreader_score": round(max_score, 4) if super_spreader else 0.0,
        "total_campaign_clusters": len(campaign_clusters),
        "clusters": campaign_clusters,
    }

    if super_spreader:
        log.info(
            f"Graph Analytics: Account {super_spreader} is the propagation hub (score {max_score:.4f}); {len(campaign_clusters)} campaign clusters found."
        )

    return result
