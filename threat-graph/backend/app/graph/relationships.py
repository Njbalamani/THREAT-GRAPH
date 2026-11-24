from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.graph.factory import get_graph_store
from app.graph.keys import event_key, extracted_key, indicator_key
from app.graph.types import GraphEdge, GraphNode
from app.models.enums import IndicatorType, Provenance, Severity
from app.models.threat import GraphRelationship, Indicator, SecurityEvent

SEVERITY_SCORE = {
    Severity.LOW: 0.25,
    Severity.MEDIUM: 0.5,
    Severity.HIGH: 0.8,
    Severity.CRITICAL: 1.0,
}


def indicator_node(indicator: Indicator) -> GraphNode:
    return GraphNode(
        key=indicator_key(indicator.id),
        type="indicator",
        label=indicator.value,
        id=indicator.id,
        properties={
            "id": indicator.id,
            "indicator_type": indicator.type.value,
            "severity": indicator.severity.value,
            "confidence": indicator.confidence,
            "source": indicator.source,
            "tags": indicator.tags,
            "is_confirmed": indicator.is_confirmed,
        },
    )


def event_node(event: SecurityEvent) -> GraphNode:
    return GraphNode(
        key=event_key(event.id),
        type="event",
        label=event.title or event.event_type,
        id=event.id,
        properties={
            "id": event.id,
            "event_type": event.event_type,
            "severity": event.severity.value,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "source": event.source,
        },
    )


def sync_indicator_nodes(db: Session, indicators: list[Indicator] | None = None) -> int:
    if indicators is None:
        indicators = list(db.scalars(select(Indicator)).all())
    store = get_graph_store()
    store.upsert_many([indicator_node(indicator) for indicator in indicators], [])
    return len(indicators)


def _find_indicator(
    lookup: dict[tuple[str, str], Indicator],
    indicator_type: IndicatorType,
    value: str | None,
) -> Indicator | None:
    if not value:
        return None
    return lookup.get((indicator_type.value, value.strip().lower()))


def _node_key_for_value(
    lookup: dict[tuple[str, str], Indicator],
    indicator_type: IndicatorType,
    value: str,
) -> tuple[str, GraphNode | None]:
    indicator = _find_indicator(lookup, indicator_type, value)
    if indicator:
        return indicator_key(indicator.id), indicator_node(indicator)
    normalized = value.strip().lower()
    key = extracted_key(indicator_type.value, normalized)
    return key, GraphNode(
        key=key,
        type="indicator",
        label=normalized,
        properties={
            "indicator_type": indicator_type.value,
            "severity": "medium",
            "source": "extracted",
            "is_confirmed": False,
        },
    )


def _record_relationship(db: Session, edge: GraphEdge) -> bool:
    existing = db.scalar(
        select(GraphRelationship).where(
            GraphRelationship.source_key == edge.source,
            GraphRelationship.target_key == edge.target,
            GraphRelationship.relation_type == edge.relationship,
            GraphRelationship.provenance == Provenance(edge.provenance),
        )
    )
    if existing:
        existing.confidence = edge.confidence
        existing.strength = edge.strength
        existing.evidence = edge.properties
        existing.source = str(edge.properties.get("source", existing.source))
        return False
    db.add(
        GraphRelationship(
            source_key=edge.source,
            target_key=edge.target,
            source_type=edge.source.split(":", 1)[0],
            target_type=edge.target.split(":", 1)[0],
            relation_type=edge.relationship,
            provenance=Provenance(edge.provenance),
            confidence=edge.confidence,
            strength=edge.strength,
            evidence=edge.properties,
            source=str(edge.properties.get("source", "relationship-engine")),
        )
    )
    return True


def build_relationships(
    db: Session,
    *,
    event_ids: list[str] | None = None,
    rebuild: bool = False,
) -> dict[str, Any]:
    store = get_graph_store()
    if rebuild:
        store.clear()
        db.execute(delete(GraphRelationship))
        db.commit()

    stmt = select(SecurityEvent)
    if event_ids:
        stmt = stmt.where(SecurityEvent.id.in_(event_ids))
    events = list(db.scalars(stmt.order_by(SecurityEvent.timestamp)).all())
    indicators = list(db.scalars(select(Indicator)).all())
    lookup = {(indicator.type.value, indicator.value.strip().lower()): indicator for indicator in indicators}

    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    domain_ip: dict[str, set[str]] = defaultdict(set)
    hash_ip: dict[str, set[str]] = defaultdict(set)

    for event in events:
        event_node_obj = event_node(event)
        nodes[event_node_obj.key] = event_node_obj
        event_key_value = event_node_obj.key
        severity = SEVERITY_SCORE.get(event.severity, 0.5)
        event_props = {
            "event_id": event.id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "severity": event.severity.value,
            "source": event.source,
        }

        extracted: list[tuple[IndicatorType, str, str, float]] = []
        if event.source_ip:
            extracted.append((IndicatorType.IP, event.source_ip, "source_ip_linked", 0.95))
        if event.destination_ip:
            extracted.append((IndicatorType.IP, event.destination_ip, "destination_ip_linked", 0.9))
        if event.domain:
            extracted.append((IndicatorType.DOMAIN, event.domain, "domain_observed", 0.9))
        if event.file_hash:
            extracted.append((IndicatorType.HASH, event.file_hash, "hash_observed", 0.95))
        if event.url:
            extracted.append((IndicatorType.URL, event.url, "url_observed", 0.85))

        keys: dict[IndicatorType, str] = {}
        for indicator_type, value, relationship, confidence in extracted:
            key, node = _node_key_for_value(lookup, indicator_type, value)
            if node:
                nodes[key] = node
            keys.setdefault(indicator_type, key)
            edge = GraphEdge(
                source=key,
                target=event_key_value,
                relationship=relationship,
                provenance=Provenance.OBSERVED.value,
                confidence=confidence,
                strength=round(severity * confidence, 3),
                properties={**event_props, "relationship_context": relationship},
            )
            edges[edge.key] = edge

        source_ip_key = keys.get(IndicatorType.IP)
        if event.source_ip:
            source_ip_key = _node_key_for_value(lookup, IndicatorType.IP, event.source_ip)[0]
        destination_ip_key = _node_key_for_value(lookup, IndicatorType.IP, event.destination_ip)[0] if event.destination_ip else None
        domain_key = _node_key_for_value(lookup, IndicatorType.DOMAIN, event.domain)[0] if event.domain else None
        hash_key = _node_key_for_value(lookup, IndicatorType.HASH, event.file_hash)[0] if event.file_hash else None

        if source_ip_key and destination_ip_key and source_ip_key != destination_ip_key:
            edge = GraphEdge(
                source=source_ip_key,
                target=destination_ip_key,
                relationship="communicated_with",
                provenance=Provenance.OBSERVED.value,
                confidence=0.85,
                strength=round(severity * 0.85, 3),
                properties={**event_props, "relationship_context": "network_communication"},
            )
            edges[edge.key] = edge

        if source_ip_key and domain_key:
            edge = GraphEdge(
                source=source_ip_key,
                target=domain_key,
                relationship="contacted_domain",
                provenance=Provenance.OBSERVED.value,
                confidence=0.75,
                strength=round(severity * 0.75, 3),
                properties={**event_props, "relationship_context": "domain_contact"},
            )
            edges[edge.key] = edge
            domain_ip[event.domain.strip().lower()].add(source_ip_key)

        if source_ip_key and hash_key:
            edge = GraphEdge(
                source=source_ip_key,
                target=hash_key,
                relationship="transferred_hash",
                provenance=Provenance.OBSERVED.value,
                confidence=0.7,
                strength=round(severity * 0.7, 3),
                properties={**event_props, "relationship_context": "file_transfer"},
            )
            edges[edge.key] = edge
            hash_ip[event.file_hash.strip().lower()].add(source_ip_key)

    for domain, ip_keys in domain_ip.items():
        if len(ip_keys) < 2:
            continue
        ordered = sorted(ip_keys)
        for left_index, left in enumerate(ordered[:12]):
            for right in ordered[left_index + 1 : 12]:
                edge = GraphEdge(
                    source=left,
                    target=right,
                    relationship="shared_domain",
                    provenance=Provenance.INFERRED.value,
                    confidence=0.45,
                    strength=0.35,
                    properties={
                        "reason": "Multiple source IPs observed contacting the same domain",
                        "evidence": {"domain": domain},
                        "source": "relationship-engine",
                    },
                )
                edges[edge.key] = edge

    for file_hash, ip_keys in hash_ip.items():
        if len(ip_keys) < 2:
            continue
        ordered = sorted(ip_keys)
        for left_index, left in enumerate(ordered[:12]):
            for right in ordered[left_index + 1 : 12]:
                edge = GraphEdge(
                    source=left,
                    target=right,
                    relationship="shared_hash",
                    provenance=Provenance.INFERRED.value,
                    confidence=0.5,
                    strength=0.4,
                    properties={
                        "reason": "Multiple source IPs observed with the same file hash",
                        "evidence": {"file_hash": file_hash},
                        "source": "relationship-engine",
                    },
                )
                edges[edge.key] = edge

    edge_list = list(edges.values())
    store.upsert_many(list(nodes.values()), edge_list)
    created = sum(_record_relationship(db, edge) for edge in edge_list)
    db.commit()

    return {
        "events_processed": len(events),
        "nodes_upserted": len(nodes),
        "edges_upserted": len(edge_list),
        "relationships_created": created,
        "observed_edges": sum(1 for edge in edge_list if edge.provenance == Provenance.OBSERVED.value),
        "inferred_edges": sum(1 for edge in edge_list if edge.provenance == Provenance.INFERRED.value),
        "backend": store.backend_name,
    }
