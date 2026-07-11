"""Campaign Clustering — build-map ticket #23.

Periodically clusters open cases by shared fingerprint (registrar, phrasing,
amount bucket, voice-print) and surfaces them in the Home tab.

Build-map spec: "Two related cases appear grouped in the Home tab unprompted."

Architecture
------------
- `build_campaign_summary()` — wraps `find_campaign_clusters()` from analytics.py
  and adds semantic enrichment: cluster IDs, sizes, shared fingerprint attributes,
  and a Slack Block Kit Home-tab payload.
- `CampaignCluster` dataclass carries the rich summary for each cluster.
- The Block Kit payload is a list of Slack blocks directly usable in
  `views.publish()` for the Home tab surface.

No periodic scheduler needed for the demo — `build_campaign_summary()` is
called on demand (e.g. when the Home tab loads, or via MCP).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from .analytics import find_campaign_clusters
from .cache import get_graph

log = logging.getLogger(__name__)


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class CampaignCluster:
    cluster_id: str
    size: int
    node_ids: list[str]
    user_nodes: list[str]
    channel_nodes: list[str]
    file_nodes: list[str]
    shared_registrar: Optional[str]    # most common registrar attribute in cluster
    representative_node: str           # largest-degree node = "hub"

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "node_ids": self.node_ids,
            "user_count": len(self.user_nodes),
            "channel_count": len(self.channel_nodes),
            "file_count": len(self.file_nodes),
            "shared_registrar": self.shared_registrar,
            "representative_node": self.representative_node,
        }


@dataclass
class CampaignSummary:
    total_clusters: int
    clusters: list[CampaignCluster] = field(default_factory=list)
    singleton_count: int = 0       # isolated nodes (not clustered)

    def to_dict(self) -> dict:
        return {
            "total_clusters": self.total_clusters,
            "singleton_count": self.singleton_count,
            "clusters": [c.to_dict() for c in self.clusters],
        }

    def to_slack_blocks(self) -> list[dict]:
        """Generate a Slack Block Kit Home-tab payload for campaign clusters."""
        blocks: list[dict[str, Any]] = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🕸️ Campaign Clusters — {self.total_clusters} active",
                "emoji": True,
            },
        })

        if not self.clusters:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No multi-node campaign clusters detected. Workspace looks clean._",
                },
            })
            return blocks

        blocks.append({"type": "divider"})

        for i, cluster in enumerate(self.clusters[:10], start=1):  # cap at 10
            user_str = (
                " · ".join(f"<@{u}>" for u in cluster.user_nodes[:3])
                or "_no users_"
            )
            ch_str = (
                " · ".join(f"<#{c}>" for c in cluster.channel_nodes[:3])
                or "_no channels_"
            )
            registrar_str = (
                f" · Registrar: *{cluster.shared_registrar}*"
                if cluster.shared_registrar else ""
            )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Cluster {i}* — {cluster.size} nodes\n"
                        f"Users: {user_str}\n"
                        f"Channels: {ch_str}"
                        f"{registrar_str}"
                    ),
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Investigate", "emoji": True},
                    "value": cluster.representative_node,
                    "action_id": f"investigate_cluster_{cluster.cluster_id[:8]}",
                },
            })

        if self.singleton_count:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_{self.singleton_count} isolated node(s) not shown_",
                    }
                ],
            })

        return blocks


# ── Main entry point ───────────────────────────────────────────────────────────

def build_campaign_summary(
    nodes: Optional[list[str]] = None,
    min_cluster_size: int = 2,
) -> CampaignSummary:
    """Build the campaign summary from the current graph cache.

    Parameters
    ----------
    nodes : list[str] | None
        Restrict clustering to a subset of node IDs (e.g. from blast radius).
        None = entire graph.
    min_cluster_size : int
        Clusters smaller than this are counted as singletons.

    Returns
    -------
    CampaignSummary
        Rich summary with Slack Block Kit payload ready to publish.
    """
    G = get_graph()
    raw_clusters: list[set[str]] = find_campaign_clusters(nodes)

    clusters: list[CampaignCluster] = []
    singleton_count = 0

    for raw in raw_clusters:
        if len(raw) < min_cluster_size:
            singleton_count += len(raw)
            continue

        node_ids = list(raw)
        users = [n for n in node_ids if G.nodes.get(n, {}).get("node_type") == "user"]
        channels = [n for n in node_ids if G.nodes.get(n, {}).get("node_type") == "channel"]
        files = [n for n in node_ids if G.nodes.get(n, {}).get("node_type") == "file"]

        # Find the highest-degree node as representative
        subgraph = G.subgraph(node_ids)
        representative = max(node_ids, key=lambda n: subgraph.degree(n), default=node_ids[0])

        # Find shared registrar (most common registrar attr in cluster, if any)
        registrars = [
            G.nodes[n].get("registrar")
            for n in node_ids
            if G.nodes.get(n, {}).get("registrar")
        ]
        shared_registrar: Optional[str] = None
        if registrars:
            from collections import Counter
            most_common = Counter(registrars).most_common(1)
            if most_common:
                shared_registrar = most_common[0][0]

        clusters.append(CampaignCluster(
            cluster_id=str(uuid.uuid4()),
            size=len(node_ids),
            node_ids=node_ids,
            user_nodes=users,
            channel_nodes=channels,
            file_nodes=files,
            shared_registrar=shared_registrar,
            representative_node=representative,
        ))

    # Sort clusters by size descending
    clusters.sort(key=lambda c: -c.size)

    log.info(
        "campaign: %d cluster(s) found (min_size=%d), %d singleton(s)",
        len(clusters), min_cluster_size, singleton_count,
    )

    return CampaignSummary(
        total_clusters=len(clusters),
        clusters=clusters,
        singleton_count=singleton_count,
    )
