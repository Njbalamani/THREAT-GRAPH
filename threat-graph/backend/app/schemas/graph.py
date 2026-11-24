from pydantic import BaseModel, Field

from app.models.enums import Provenance


class GraphNode(BaseModel):
    key: str
    id: str
    type: str
    label: str
    properties: dict = Field(default_factory=dict)
    degree: int = 0
    risk_score: float | None = None


class GraphEdge(BaseModel):
    key: str
    source: str
    target: str
    relationship: str
    provenance: Provenance
    confidence: float
    strength: float
    properties: dict = Field(default_factory=dict)


class GraphSnapshot(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphStats(BaseModel):
    node_count: int
    edge_count: int
    observed_edges: int
    inferred_edges: int
    node_types: dict[str, int]
    relationship_types: dict[str, int]
    average_degree: float


class NeighborQuery(BaseModel):
    key: str
    depth: int = Field(default=1, ge=1, le=5)


class PathQuery(BaseModel):
    source: str
    target: str
    max_depth: int = Field(default=6, ge=1, le=12)


class RelationshipIn(BaseModel):
    source_key: str
    target_key: str
    source_type: str
    target_type: str
    relationship: str
    provenance: Provenance = Provenance.OBSERVED
    confidence: float = Field(default=0.5, ge=0, le=1)
    strength: float = Field(default=0.5, ge=0, le=1)
    evidence: dict = Field(default_factory=dict)
