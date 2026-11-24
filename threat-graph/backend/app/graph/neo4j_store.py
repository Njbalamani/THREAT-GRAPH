from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

import networkx as nx
from neo4j import GraphDatabase

from app.graph.base import GraphStore
from app.graph.types import GraphEdge, GraphNode


def flat(value: Any) -> Any:
    if isinstance(value, (dict, list, set, tuple)):
        return json.dumps(_jsonable(value), default=str)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


class Neo4jGraphStore(GraphStore):
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password), database=database)
        self.setup_constraints()

    @property
    def backend_name(self) -> str:
        return "neo4j"

    def verify(self) -> None:
        with self.driver.session() as session:
            result = session.run("RETURN 1 AS ok")
            if not result.single()["ok"]:
                raise RuntimeError("Neo4j verification failed")

    def setup_constraints(self) -> None:
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT threatgraph_node_key IF NOT EXISTS FOR (n:ThreatNode) REQUIRE n.key IS UNIQUE")
            session.run("CREATE CONSTRAINT threatgraph_edge_key IF NOT EXISTS FOR ()-[r:RELATES]-() REQUIRE r.key IS UNIQUE")

    def close(self) -> None:
        self.driver.close()

    def upsert_node(self, node: GraphNode) -> None:
        properties = {"id": node.id, **flat(node.properties)}
        with self.driver.session() as session:
            session.run(
                """
                MERGE (n:ThreatNode {key: $key})
                SET n.label = $label,
                    n.node_type = $node_type,
                    n.updated_at = datetime(),
                    n += $properties
                """,
                key=node.key,
                label=node.label,
                node_type=node.type,
                properties=properties,
            )

    def upsert_edge(self, edge: GraphEdge) -> None:
        properties = flat(edge.properties)
        with self.driver.session() as session:
            session.run(
                """
                MATCH (s:ThreatNode {key: $source})
                MATCH (t:ThreatNode {key: $target})
                MERGE (s)-[r:RELATES {key: $key}]->(t)
                SET r.relationship = $relationship,
                    r.provenance = $provenance,
                    r.confidence = $confidence,
                    r.strength = $strength,
                    r.updated_at = datetime(),
                    r += $properties
                """,
                source=edge.source,
                target=edge.target,
                key=edge.key,
                relationship=edge.relationship,
                provenance=edge.provenance,
                confidence=edge.confidence,
                strength=edge.strength,
                properties=properties,
            )

    def get_nodes(
        self,
        limit: int = 500,
        node_type: str | None = None,
        search: str | None = None,
    ) -> list[GraphNode]:
        query = """
        MATCH (n:ThreatNode)
        WHERE ($node_type IS NULL OR n.node_type = $node_type)
          AND ($search IS NULL OR toLower(n.label) CONTAINS toLower($search))
        RETURN n.key AS key, n.label AS label, n.node_type AS type,
               properties(n) AS properties, size((n)--()) AS degree
        ORDER BY n.label
        LIMIT $limit
        """
        with self.driver.session() as session:
            records = session.run(query, node_type=node_type, search=search, limit=limit)
            result = []
            for record in records:
                props = dict(record["properties"])
                node = GraphNode(
                    key=record["key"],
                    type=record["type"],
                    label=record["label"],
                    properties=props,
                    id=str(props.get("id") or record["key"].split(":", 1)[-1]),
                )
                node.properties["degree"] = record["degree"]
                result.append(node)
            return result

    def get_edges(
        self,
        limit: int = 1000,
        provenance: str | None = None,
        relationship: str | None = None,
    ) -> list[GraphEdge]:
        query = """
        MATCH (s:ThreatNode)-[r:RELATES]->(t:ThreatNode)
        WHERE ($provenance IS NULL OR r.provenance = $provenance)
          AND ($relationship IS NULL OR r.relationship = $relationship)
        RETURN s.key AS source, t.key AS target, r.relationship AS relationship,
               r.provenance AS provenance, r.confidence AS confidence,
               r.strength AS strength, properties(r) AS properties
        LIMIT $limit
        """
        with self.driver.session() as session:
            records = session.run(
                query,
                provenance=provenance,
                relationship=relationship,
                limit=limit,
            )
            return [
                GraphEdge(
                    source=record["source"],
                    target=record["target"],
                    relationship=record["relationship"],
                    provenance=record["provenance"],
                    confidence=float(record["confidence"]),
                    strength=float(record["strength"]),
                    properties=dict(record["properties"]),
                )
                for record in records
            ]

    def get_snapshot(self, limit: int = 500) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes = self.get_nodes(limit=limit)
        keys = {node.key for node in nodes}
        edges = [edge for edge in self.get_edges(limit=limit * 4) if edge.source in keys and edge.target in keys]
        return nodes, edges

    def neighbors(self, key: str, depth: int = 1) -> tuple[list[GraphNode], list[GraphEdge]]:
        query = """
        MATCH p = (start:ThreatNode {key: $key})-[*0..$depth]-(other:ThreatNode)
        WITH DISTINCT nodes(p) AS ns, relationships(p) AS rs
        UNWIND ns AS n
        WITH collect(DISTINCT n) AS nodeList, reduce(acc = [], r IN rs | acc + [r]) AS rels
        RETURN [n IN nodeList | {
            key: n.key,
            label: n.label,
            type: n.node_type,
            properties: properties(n),
            degree: size((n)--())
        }] AS nodes,
        [r IN rels | {
            key: r.key,
            source: startNode(r).key,
            target: endNode(r).key,
            relationship: r.relationship,
            provenance: r.provenance,
            confidence: r.confidence,
            strength: r.strength,
            properties: properties(r)
        }] AS edges
        """
        with self.driver.session() as session:
            record = session.run(query, key=key, depth=depth).single()
            if not record:
                return [], []
            nodes = []
            for item in record["nodes"]:
                props = dict(item["properties"])
                nodes.append(
                    GraphNode(
                        key=item["key"],
                        type=item["type"],
                        label=item["label"],
                        properties={**props, "degree": item["degree"]},
                        id=str(props.get("id") or item["key"].split(":", 1)[-1]),
                    )
                )
            edges = [
                GraphEdge(
                    source=item["source"],
                    target=item["target"],
                    relationship=item["relationship"],
                    provenance=item["provenance"],
                    confidence=float(item["confidence"]),
                    strength=float(item["strength"]),
                    properties=dict(item["properties"]),
                )
                for item in record["edges"]
            ]
            return nodes, edges

    def shortest_path(self, source: str, target: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        if source == target:
            return self.neighbors(source, depth=0)
        query = """
        MATCH p = shortestPath((s:ThreatNode {key: $source})-[*..12]-(t:ThreatNode {key: $target}))
        RETURN [n IN nodes(p) | {
            key: n.key,
            label: n.label,
            type: n.node_type,
            properties: properties(n),
            degree: size((n)--())
        }] AS nodes,
        [r IN relationships(p) | {
            source: startNode(r).key,
            target: endNode(r).key,
            relationship: r.relationship,
            provenance: r.provenance,
            confidence: r.confidence,
            strength: r.strength,
            properties: properties(r)
        }] AS edges
        """
        with self.driver.session() as session:
            record = session.run(query, source=source, target=target).single()
            if not record:
                return [], []
            nodes = []
            for item in record["nodes"]:
                props = dict(item["properties"])
                nodes.append(
                    GraphNode(
                        key=item["key"],
                        type=item["type"],
                        label=item["label"],
                        properties={**props, "degree": item["degree"]},
                        id=str(props.get("id") or item["key"].split(":", 1)[-1]),
                    )
                )
            edges = [
                GraphEdge(
                    source=item["source"],
                    target=item["target"],
                    relationship=item["relationship"],
                    provenance=item["provenance"],
                    confidence=float(item["confidence"]),
                    strength=float(item["strength"]),
                    properties=dict(item["properties"]),
                )
                for item in record["edges"]
            ]
            return nodes, edges

    def stats(self) -> dict:
        query = """
        MATCH (n:ThreatNode)
        WITH count(n) AS node_count
        OPTIONAL MATCH ()-[r:RELATES]->()
        RETURN node_count, count(r) AS edge_count
        """
        with self.driver.session() as session:
            counts = session.run(query).single()
            node_count = int(counts["node_count"])
            edge_count = int(counts["edge_count"])
            provenance = session.run(
                """
                MATCH ()-[r:RELATES]->()
                RETURN r.provenance AS provenance, count(r) AS total
                """
            )
            relationships = session.run(
                """
                MATCH ()-[r:RELATES]->()
                RETURN r.relationship AS relationship, count(r) AS total
                """
            )
            types = session.run(
                """
                MATCH (n:ThreatNode)
                RETURN n.node_type AS node_type, count(n) AS total
                """
            )
            prov_counts = {record["provenance"]: record["total"] for record in provenance}
            rel_counts = {record["relationship"]: record["total"] for record in relationships}
            type_counts = {record["node_type"]: record["total"] for record in types}
            return {
                "node_count": node_count,
                "edge_count": edge_count,
                "observed_edges": int(prov_counts.get("observed", 0)),
                "inferred_edges": int(prov_counts.get("inferred", 0)),
                "node_types": {str(k): int(v) for k, v in type_counts.items()},
                "relationship_types": {str(k): int(v) for k, v in rel_counts.items()},
                "average_degree": round((2 * edge_count / node_count) if node_count else 0, 3),
            }

    def clear(self) -> None:
        with self.driver.session() as session:
            session.run("MATCH (n:ThreatNode) DETACH DELETE n")

    def export_graphml(self, path: Path) -> Path:
        nodes, edges = self.get_snapshot(limit=5000)
        path.parent.mkdir(parents=True, exist_ok=True)
        export = nx.MultiDiGraph()
        for node in nodes:
            export.add_node(
                node.key,
                label=node.label,
                node_type=node.type,
                properties=json.dumps(_jsonable(node.properties)),
            )
        for edge in edges:
            export.add_edge(
                edge.source,
                edge.target,
                key=edge.key,
                relationship=edge.relationship,
                provenance=edge.provenance,
                confidence=edge.confidence,
                strength=edge.strength,
                properties=json.dumps(_jsonable(edge.properties)),
            )
        nx.write_graphml(export, path)
        return path
