from __future__ import annotations

import json
import os
import threading
from collections import Counter
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

import networkx as nx

from app.graph.base import GraphStore
from app.graph.types import GraphEdge, GraphNode


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


class NetworkXGraphStore(GraphStore):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = nx.MultiDiGraph()
        self.lock = threading.RLock()
        self._load()

    @property
    def backend_name(self) -> str:
        return "networkx"

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        with self.lock:
            for node in data.get("nodes", []):
                key = node.get("key")
                if key:
                    self.graph.add_node(
                        key,
                        type=node.get("type", "unknown"),
                        label=node.get("label", key),
                        properties=node.get("properties", {}),
                    )
            for edge in data.get("edges", []):
                source = edge.get("source")
                target = edge.get("target")
                if not source or not target:
                    continue
                attrs = {
                    "key": edge.get("key"),
                    "relationship": edge.get("relationship", "related_to"),
                    "provenance": edge.get("provenance", "observed"),
                    "confidence": float(edge.get("confidence", 0.5)),
                    "strength": float(edge.get("strength", 0.5)),
                    "properties": edge.get("properties", {}),
                }
                self.graph.add_edge(
                    source,
                    target,
                    key=attrs["key"],
                    relationship=attrs["relationship"],
                    provenance=attrs["provenance"],
                    confidence=attrs["confidence"],
                    strength=attrs["strength"],
                    properties=attrs["properties"],
                )

    def _save(self) -> None:
        payload = {
            "nodes": [
                {
                    "key": key,
                    "type": attrs.get("type", "unknown"),
                    "label": attrs.get("label", key),
                    "properties": jsonable(attrs.get("properties", {})),
                }
                for key, attrs in self.graph.nodes(data=True)
            ],
            "edges": [
                {
                    "key": attrs.get("key"),
                    "source": source,
                    "target": target,
                    "relationship": attrs.get("relationship"),
                    "provenance": attrs.get("provenance"),
                    "confidence": attrs.get("confidence"),
                    "strength": attrs.get("strength"),
                    "properties": jsonable(attrs.get("properties", {})),
                }
                for source, target, attrs in self.graph.edges(data=True)
            ],
        }
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temp, self.path)

    def upsert_node(self, node: GraphNode) -> None:
        with self.lock:
            if self.graph.has_node(node.key):
                self.graph.nodes[node.key].update(
                    type=node.type,
                    label=node.label,
                    properties={**self.graph.nodes[node.key].get("properties", {}), **jsonable(node.properties)},
                )
            else:
                self.graph.add_node(
                    node.key,
                    type=node.type,
                    label=node.label,
                    properties=jsonable(node.properties),
                )
            self._save()

    def upsert_edge(self, edge: GraphEdge) -> None:
        with self.lock:
            if not self.graph.has_node(edge.source):
                self.graph.add_node(edge.source, type="unknown", label=edge.source, properties={})
            if not self.graph.has_node(edge.target):
                self.graph.add_node(edge.target, type="unknown", label=edge.target, properties={})
            if self.graph.has_edge(edge.source, edge.target):
                for _, attrs in self.graph[edge.source][edge.target].items():
                    if attrs.get("key") == edge.key:
                        attrs.update(
                            confidence=edge.confidence,
                            strength=edge.strength,
                            properties={**attrs.get("properties", {}), **jsonable(edge.properties)},
                        )
                        self._save()
                        return
            self.graph.add_edge(
                edge.source,
                edge.target,
                key=edge.key,
                relationship=edge.relationship,
                provenance=edge.provenance,
                confidence=edge.confidence,
                strength=edge.strength,
                properties=jsonable(edge.properties),
            )
            self._save()

    def _node_from_graph(self, key: str, attrs: dict) -> GraphNode:
        properties = attrs.get("properties", {})
        return GraphNode(
            key=key,
            type=attrs.get("type", "unknown"),
            label=attrs.get("label", key),
            properties=properties,
            id=str(properties.get("id") or key.split(":", 1)[-1]),
        )

    def _edge_from_graph(self, source: str, target: str, attrs: dict) -> GraphEdge:
        return GraphEdge(
            source=source,
            target=target,
            relationship=attrs.get("relationship", "related_to"),
            provenance=attrs.get("provenance", "observed"),
            confidence=float(attrs.get("confidence", 0.5)),
            strength=float(attrs.get("strength", 0.5)),
            properties=attrs.get("properties", {}),
        )

    def get_nodes(self, limit: int = 500, node_type: str | None = None, search: str | None = None) -> list[GraphNode]:
        result: list[GraphNode] = []
        with self.lock:
            for key, attrs in self.graph.nodes(data=True):
                if node_type and attrs.get("type") != node_type:
                    continue
                if search and search.lower() not in str(attrs.get("label", "")).lower():
                    continue
                node = self._node_from_graph(key, attrs)
                node.properties["degree"] = self.graph.degree(key)
                result.append(node)
                if len(result) >= limit:
                    break
        return result

    def get_edges(
        self,
        limit: int = 1000,
        provenance: str | None = None,
        relationship: str | None = None,
    ) -> list[GraphEdge]:
        result: list[GraphEdge] = []
        with self.lock:
            for source, target, attrs in self.graph.edges(data=True):
                if provenance and attrs.get("provenance") != provenance:
                    continue
                if relationship and attrs.get("relationship") != relationship:
                    continue
                result.append(self._edge_from_graph(source, target, attrs))
                if len(result) >= limit:
                    break
        return result

    def get_snapshot(self, limit: int = 500) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes = self.get_nodes(limit=limit)
        keys = {node.key for node in nodes}
        edges = [edge for edge in self.get_edges(limit=limit * 4) if edge.source in keys and edge.target in keys]
        return nodes, edges

    def neighbors(self, key: str, depth: int = 1) -> tuple[list[GraphNode], list[GraphEdge]]:
        with self.lock:
            if not self.graph.has_node(key):
                return [], []
            visible: set[str] = {key}
            frontier = {key}
            for _ in range(depth):
                next_frontier: set[str] = set()
                for node in frontier:
                    next_frontier.update(self.graph.neighbors(node))
                visible.update(next_frontier)
                frontier = next_frontier
            subgraph = self.graph.subgraph(visible)
            nodes = [self._node_from_graph(node_key, attrs) for node_key, attrs in subgraph.nodes(data=True)]
            edges = [self._edge_from_graph(source, target, attrs) for source, target, attrs in subgraph.edges(data=True)]
            return nodes, edges

    def shortest_path(self, source: str, target: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        with self.lock:
            undirected = self.graph.to_undirected()
            if source not in undirected or target not in undirected or not nx.has_path(undirected, source, target):
                return [], []
            path = nx.shortest_path(undirected, source, target)
            nodes = [self._node_from_graph(key, self.graph.nodes[key]) for key in path]
            edges: list[GraphEdge] = []
            for a, b in zip(path, path[1:], strict=False):
                if self.graph.has_edge(a, b):
                    key = next(iter(self.graph[a][b]), None)
                    if key is not None:
                        edges.append(self._edge_from_graph(a, b, self.graph[a][b][key]))
                elif self.graph.has_edge(b, a):
                    key = next(iter(self.graph[b][a]), None)
                    if key is not None:
                        edges.append(self._edge_from_graph(a, b, self.graph[b][a][key]))
            return nodes, edges

    def stats(self) -> dict:
        with self.lock:
            edge_count = self.graph.number_of_edges()
            nodes = self.graph.number_of_nodes()
            relationship_types = Counter(attrs.get("relationship", "unknown") for _, _, attrs in self.graph.edges(data=True))
            return {
                "node_count": nodes,
                "edge_count": edge_count,
                "observed_edges": sum(1 for _, _, attrs in self.graph.edges(data=True) if attrs.get("provenance") == "observed"),
                "inferred_edges": sum(1 for _, _, attrs in self.graph.edges(data=True) if attrs.get("provenance") == "inferred"),
                "node_types": dict(Counter(attrs.get("type", "unknown") for _, attrs in self.graph.nodes(data=True))),
                "relationship_types": dict(relationship_types),
                "average_degree": round((2 * edge_count / nodes) if nodes else 0, 3),
            }

    def clear(self) -> None:
        with self.lock:
            self.graph.clear()
            self._save()

    def export_graphml(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            export = nx.MultiDiGraph()
            for key, attrs in self.graph.nodes(data=True):
                export.add_node(
                    key,
                    label=str(attrs.get("label", key)),
                    node_type=str(attrs.get("type", "unknown")),
                    properties=json.dumps(jsonable(attrs.get("properties", {}))),
                )
            for source, target, attrs in self.graph.edges(data=True):
                export.add_edge(
                    source,
                    target,
                    key=str(attrs.get("key", "")),
                    relationship=str(attrs.get("relationship", "related_to")),
                    provenance=str(attrs.get("provenance", "observed")),
                    confidence=float(attrs.get("confidence", 0.5)),
                    strength=float(attrs.get("strength", 0.5)),
                    properties=json.dumps(jsonable(attrs.get("properties", {}))),
                )
            nx.write_graphml(export, path)
        return path
