from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import networkx as nx
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.graph.base import GraphStore
from app.graph.keys import indicator_key
from app.models.enums import IndicatorType, Severity
from app.models.threat import Indicator, SecurityEvent

FEATURE_NAMES = [
    "event_count",
    "distinct_event_types",
    "severity_score",
    "confidence",
    "age_days",
    "tag_hits",
    "graph_degree",
    "betweenness",
    "community_size",
    "is_ip",
    "is_domain",
    "is_hash",
]

SEVERITY_SCORE = {
    Severity.LOW: 0.25,
    Severity.MEDIUM: 0.5,
    Severity.HIGH: 0.8,
    Severity.CRITICAL: 1.0,
}

SUSPICIOUS_TAGS = {"malicious", "suspicious", "phishing", "c2", "ransomware", "botnet", "exploit"}


def _community_sizes(store: GraphStore, keys: set[str]) -> dict[str, int]:
    try:
        nodes, edges = store.get_snapshot(limit=5000)
        graph = nx.Graph()
        graph.add_nodes_from(node.key for node in nodes if node.key in keys)
        for edge in edges:
            if edge.source in keys and edge.target in keys:
                graph.add_edge(edge.source, edge.target)
        communities = nx.algorithms.community.greedy_modularity_communities(graph)
        return {key: len(community) for community in communities for key in community}
    except (nx.NetworkXError, ValueError):
        return {}


def _betweenness(store: GraphStore, keys: set[str]) -> dict[str, float]:
    try:
        nodes, edges = store.get_snapshot(limit=5000)
        graph = nx.Graph()
        graph.add_nodes_from(node.key for node in nodes if node.key in keys)
        for edge in edges:
            if edge.source in keys and edge.target in keys:
                graph.add_edge(edge.source, edge.target)
        if graph.number_of_nodes() < 3:
            return {}
        return nx.betweenness_centrality(graph, normalized=True, seed=42)
    except (nx.NetworkXError, ValueError):
        return {}


def build_feature_rows(db: Session, store: GraphStore) -> list[dict[str, Any]]:
    indicators = list(db.scalars(select(Indicator).order_by(Indicator.first_seen)).all())
    events = list(db.scalars(select(SecurityEvent)).all())
    keys = {indicator_key(indicator.id) for indicator in indicators}
    node_map = {node.key: node for node in store.get_nodes(limit=5000)}
    communities = _community_sizes(store, keys)
    betweenness = _betweenness(store, keys)

    feature_rows: list[dict[str, Any]] = []
    for indicator in indicators:
        value = indicator.value.lower()
        indicator_type = indicator.type
        matching = []
        for event in events:
            candidates = []
            if indicator_type == IndicatorType.IP:
                candidates = [event.source_ip, event.destination_ip]
            elif indicator_type == IndicatorType.DOMAIN:
                candidates = [event.domain]
            elif indicator_type == IndicatorType.HASH:
                candidates = [event.file_hash]
            elif indicator_type == IndicatorType.URL:
                candidates = [event.url]
            if any(candidate and str(candidate).lower() == value for candidate in candidates):
                matching.append(event)

        key = indicator_key(indicator.id)
        node = node_map.get(key)
        degree = int((node.properties or {}).get("degree", 0)) if node else 0
        age_days = max(0.0, (datetime.now(UTC).replace(tzinfo=None) - indicator.last_seen).total_seconds() / 86400)
        tag_hits = sum(1 for tag in indicator.tags or [] if str(tag).lower() in SUSPICIOUS_TAGS)
        last_event = max((event.timestamp for event in matching), default=None)
        recency_boost = 0.0
        if last_event:
            recency_boost = max(0.0, 1 - (datetime.now(UTC).replace(tzinfo=None) - last_event).days / 180)

        features = {
            "event_count": min(len(matching), 50) / 10,
            "distinct_event_types": len({event.event_type for event in matching}),
            "severity_score": SEVERITY_SCORE.get(indicator.severity, 0.5),
            "confidence": indicator.confidence,
            "age_days": min(age_days, 365) / 365,
            "tag_hits": min(tag_hits, 5),
            "graph_degree": min(degree, 100) / 10,
            "betweenness": betweenness.get(key, 0.0),
            "community_size": min(communities.get(key, 0), 100) / 10,
            "is_ip": float(indicator_type == IndicatorType.IP),
            "is_domain": float(indicator_type == IndicatorType.DOMAIN),
            "is_hash": float(indicator_type == IndicatorType.HASH),
        }

        if indicator.is_confirmed:
            label = 1
            label_source = "analyst_or_trusted_feed"
        elif indicator.severity in {Severity.HIGH, Severity.CRITICAL} and tag_hits:
            label = 1
            label_source = "heuristic"
        elif len(matching) >= 3 and indicator.severity in {Severity.HIGH, Severity.CRITICAL}:
            label = 1
            label_source = "heuristic"
        else:
            label = 0
            label_source = "heuristic"

        feature_rows.append(
            {
                "indicator": indicator,
                "features": features,
                "vector": [features[name] for name in FEATURE_NAMES],
                "label": label,
                "label_source": label_source,
                "recency_boost": recency_boost,
            }
        )
    return feature_rows


def matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([row["vector"] for row in rows], dtype=float)
