from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean, pstdev
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.graph.base import GraphStore
from app.graph.types import GraphEdge
from app.models.enums import Provenance, Severity
from app.models.threat import GraphRelationship

SEVERITY_SCORE = {
    Severity.LOW.value: 0.25,
    Severity.MEDIUM.value: 0.5,
    Severity.HIGH.value: 0.8,
    Severity.CRITICAL.value: 1.0,
}


def _risk_score(properties: dict[str, Any]) -> float:
    return SEVERITY_SCORE.get(str(properties.get("severity", "medium")), 0.5)


def _build_graph(store: GraphStore) -> nx.MultiDiGraph:
    nodes, edges = store.get_snapshot(limit=5000)
    graph = nx.MultiDiGraph()
    for node in nodes:
        graph.add_node(node.key, label=node.label, type=node.type, properties=node.properties)
    for edge in edges:
        if graph.has_node(edge.source) and graph.has_node(edge.target):
            graph.add_edge(
                edge.source,
                edge.target,
                key=edge.key,
                relationship=edge.relationship,
                provenance=edge.provenance,
                confidence=edge.confidence,
                strength=edge.strength,
                properties=edge.properties,
            )
    return graph


def analyze_graph(store: GraphStore) -> dict[str, Any]:
    graph = _build_graph(store)
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    if node_count == 0:
        return {
            "backend": store.backend_name,
            "node_count": 0,
            "edge_count": 0,
            "clusters": [],
            "important_nodes": [],
            "anomalies": [],
            "generated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        }

    degree_centrality = nx.degree_centrality(graph)
    try:
        betweenness = nx.betweenness_centrality(graph.to_undirected(), seed=42)
    except (nx.NetworkXError, ValueError):
        betweenness = {key: 0.0 for key in graph.nodes}

    important_nodes = []
    for key, between in betweenness.items():
        attrs = graph.nodes[key]
        score = 0.55 * between + 0.45 * degree_centrality.get(key, 0)
        important_nodes.append(
            {
                "key": key,
                "label": attrs.get("label", key),
                "type": attrs.get("type", "unknown"),
                "score": round(score, 4),
                "degree": graph.degree(key),
            }
        )
    important_nodes.sort(key=lambda item: item["score"], reverse=True)

    clusters: list[dict[str, Any]] = []
    try:
        communities = nx.algorithms.community.greedy_modularity_communities(graph.to_undirected())
    except (nx.NetworkXError, ValueError):
        communities = [set(graph.nodes)]
    for cluster_id, community in enumerate(communities):
        labels = [graph.nodes[key].get("label", key) for key in community]
        risks = [_risk_score(graph.nodes[key].get("properties", {})) for key in community]
        clusters.append(
            {
                "cluster_id": cluster_id,
                "size": len(community),
                "nodes": sorted(community),
                "labels": labels[:30],
                "risk_score": round(mean(risks) if risks else 0.0, 3),
            }
        )
    clusters.sort(key=lambda item: item["risk_score"], reverse=True)

    strengths = [float(attrs.get("strength", 0.5)) for _, _, attrs in graph.edges(data=True)]
    average_strength = mean(strengths) if strengths else 0.0
    deviation = pstdev(strengths) if len(strengths) > 1 else 0.0
    anomalies: list[dict[str, Any]] = []
    for source, target, attrs in graph.edges(data=True):
        strength = float(attrs.get("strength", 0.5))
        score = (strength - average_strength) / deviation if deviation else 0.0
        if score >= 1.5:
            anomalies.append(
                {
                    "source": source,
                    "target": target,
                    "relationship": attrs.get("relationship", "related_to"),
                    "provenance": attrs.get("provenance", "observed"),
                    "score": round(score, 3),
                    "reason": "Relationship strength is unusually high compared with the graph baseline.",
                }
            )
        elif attrs.get("provenance") == "inferred" and strength >= 0.5:
            anomalies.append(
                {
                    "source": source,
                    "target": target,
                    "relationship": attrs.get("relationship", "related_to"),
                    "provenance": "inferred",
                    "score": round(strength, 3),
                    "reason": "Inferred connection has material strength and requires analyst review.",
                }
            )
    anomalies.sort(key=lambda item: item["score"], reverse=True)

    return {
        "backend": store.backend_name,
        "node_count": node_count,
        "edge_count": edge_count,
        "clusters": clusters[:30],
        "important_nodes": important_nodes[:30],
        "anomalies": anomalies[:30],
        "generated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
    }


def persist_inferred_connections(
    db: Session,
    store: GraphStore,
    analysis: dict[str, Any],
    *,
    max_edges: int = 50,
) -> int:
    existing_edges = store.get_edges(limit=10000)
    existing_pairs = {(edge.source, edge.target, edge.relationship) for edge in existing_edges}
    existing_pairs.update((edge.target, edge.source, edge.relationship) for edge in existing_edges)

    nodes = {node.key: node for node in store.get_nodes(limit=5000)}
    created = 0
    for cluster in analysis.get("clusters", []):
        indicator_keys = [key for key in cluster.get("nodes", []) if key.startswith("indicator:") and key in nodes]
        if len(indicator_keys) < 3:
            continue
        ranked = sorted(indicator_keys, key=lambda key: _risk_score(nodes[key].properties), reverse=True)[:6]
        for index, source in enumerate(ranked):
            for target in ranked[index + 1 :]:
                if created >= max_edges:
                    return created
                relationship = "similar_behaviour"
                if (source, target, relationship) in existing_pairs:
                    continue
                confidence = round(0.3 + 0.1 * float(cluster.get("risk_score", 0.5)), 3)
                evidence = {
                    "reason": "Indicators appear in the same graph community with comparable risk features",
                    "cluster_id": cluster.get("cluster_id"),
                    "cluster_size": cluster.get("size"),
                    "source": "graph-analytics",
                }
                edge = GraphEdge(
                    source=source,
                    target=target,
                    relationship=relationship,
                    provenance=Provenance.INFERRED.value,
                    confidence=confidence,
                    strength=round(confidence * 0.8, 3),
                    properties=evidence,
                )
                store.upsert_edge(edge)
                duplicate = db.scalar(
                    select(GraphRelationship).where(
                        GraphRelationship.source_key == edge.source,
                        GraphRelationship.target_key == edge.target,
                        GraphRelationship.relation_type == edge.relationship,
                        GraphRelationship.provenance == Provenance.INFERRED,
                    )
                )
                if not duplicate:
                    db.add(
                        GraphRelationship(
                            source_key=edge.source,
                            target_key=edge.target,
                            source_type="indicator",
                            target_type="indicator",
                            relation_type=edge.relationship,
                            provenance=Provenance.INFERRED,
                            confidence=edge.confidence,
                            strength=edge.strength,
                            evidence=evidence,
                            source="graph-analytics",
                        )
                    )
                created += 1
    db.commit()
    return created
