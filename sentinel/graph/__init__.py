"""Graph package — in-memory Slack workspace graph cache.

The singleton DiGraph is populated in real time from Slack's Event API
(see slack_events.py). The BFS blast-radius mapper (ticket #19) and the
PageRank super-spreader analysis (ticket #20) both query this cache locally
rather than hammering the RTS API live.
"""

from .cache import ingest_event, neighbors, get_graph_snapshot, get_graph
from .blast_radius import blast_radius, blast_radius_sync, BlastRadiusResult
from .quarantine import quarantine, lift_quarantine, is_quarantined, get_quarantine_log
from .campaign import build_campaign_summary, CampaignSummary

__all__ = [
    "ingest_event", "neighbors", "get_graph_snapshot", "get_graph",
    "blast_radius", "blast_radius_sync", "BlastRadiusResult",
    "quarantine", "lift_quarantine", "is_quarantined", "get_quarantine_log",
    "build_campaign_summary", "CampaignSummary",
]
