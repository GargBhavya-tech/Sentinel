"""Graph package — in-memory Slack workspace graph cache.

The singleton DiGraph is populated in real time from Slack's Event API
(see slack_events.py). The BFS blast-radius mapper (ticket #19) and the
PageRank super-spreader analysis (ticket #20) both query this cache locally
rather than hammering the RTS API live.
"""

from .cache import ingest_event, neighbors, get_graph_snapshot, get_graph

__all__ = ["ingest_event", "neighbors", "get_graph_snapshot", "get_graph"]
