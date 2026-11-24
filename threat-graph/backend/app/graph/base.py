from abc import ABC, abstractmethod
from pathlib import Path

from app.graph.types import GraphEdge, GraphNode


class GraphStore(ABC):
    @property
    @abstractmethod
    def backend_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def upsert_node(self, node: GraphNode) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert_edge(self, edge: GraphEdge) -> None:
        raise NotImplementedError

    def upsert_many(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        for node in nodes:
            self.upsert_node(node)
        for edge in edges:
            self.upsert_edge(edge)

    @abstractmethod
    def get_nodes(
        self,
        *,
        limit: int = 500,
        node_type: str | None = None,
        search: str | None = None,
    ) -> list[GraphNode]:
        raise NotImplementedError

    @abstractmethod
    def get_edges(
        self,
        *,
        limit: int = 1000,
        provenance: str | None = None,
        relationship: str | None = None,
    ) -> list[GraphEdge]:
        raise NotImplementedError

    @abstractmethod
    def get_snapshot(self, limit: int = 500) -> tuple[list[GraphNode], list[GraphEdge]]:
        raise NotImplementedError

    @abstractmethod
    def neighbors(self, key: str, depth: int = 1) -> tuple[list[GraphNode], list[GraphEdge]]:
        raise NotImplementedError

    @abstractmethod
    def shortest_path(self, source: str, target: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        raise NotImplementedError

    @abstractmethod
    def stats(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def export_graphml(self, path: Path) -> Path:
        raise NotImplementedError
