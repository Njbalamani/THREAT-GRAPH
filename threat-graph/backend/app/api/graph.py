from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.graph.factory import get_graph_store
from app.graph.types import GraphEdge, GraphNode
from app.models.user import User
from app.schemas.graph import GraphEdge as GraphEdgeOut
from app.schemas.graph import GraphNode as GraphNodeOut
from app.schemas.graph import GraphSnapshot, PathQuery

router = APIRouter(prefix="/graph", tags=["graph"])


def node_out(node: GraphNode) -> GraphNodeOut:
    return GraphNodeOut(
        key=node.key,
        id=node.id,
        type=node.type,
        label=node.label,
        properties=node.properties,
        degree=int(node.properties.get("degree", 0)),
        risk_score=node.properties.get("risk_score"),
    )


def edge_out(edge: GraphEdge) -> GraphEdgeOut:
    return GraphEdgeOut(
        key=edge.key,
        source=edge.source,
        target=edge.target,
        relationship=edge.relationship,
        provenance=edge.provenance,
        confidence=edge.confidence,
        strength=edge.strength,
        properties=edge.properties,
    )


@router.get("/stats")
def graph_stats(_: User = Depends(get_current_user)) -> dict:
    return get_graph_store().stats()


@router.get("/nodes", response_model=list[GraphNodeOut])
def graph_nodes(
    _: User = Depends(get_current_user),
    limit: int = Query(default=500, ge=1, le=5000),
    node_type: str | None = None,
    search: str | None = None,
) -> list[GraphNodeOut]:
    return [node_out(node) for node in get_graph_store().get_nodes(limit=limit, node_type=node_type, search=search)]


@router.get("/edges", response_model=list[GraphEdgeOut])
def graph_edges(
    _: User = Depends(get_current_user),
    limit: int = Query(default=1000, ge=1, le=10000),
    provenance: str | None = None,
    relationship: str | None = None,
) -> list[GraphEdgeOut]:
    return [
        edge_out(edge)
        for edge in get_graph_store().get_edges(
            limit=limit,
            provenance=provenance,
            relationship=relationship,
        )
    ]


@router.get("/snapshot", response_model=GraphSnapshot)
def graph_snapshot(
    _: User = Depends(get_current_user),
    limit: int = Query(default=500, ge=1, le=5000),
) -> GraphSnapshot:
    nodes, edges = get_graph_store().get_snapshot(limit=limit)
    return GraphSnapshot(nodes=[node_out(node) for node in nodes], edges=[edge_out(edge) for edge in edges])


@router.get("/neighbors", response_model=GraphSnapshot)
def graph_neighbors(
    key: str,
    _: User = Depends(get_current_user),
    depth: int = Query(default=1, ge=1, le=5),
) -> GraphSnapshot:
    nodes, edges = get_graph_store().neighbors(key, depth)
    return GraphSnapshot(nodes=[node_out(node) for node in nodes], edges=[edge_out(edge) for edge in edges])


@router.post("/path", response_model=GraphSnapshot)
def graph_path(payload: PathQuery, _: User = Depends(get_current_user)) -> GraphSnapshot:
    nodes, edges = get_graph_store().shortest_path(payload.source, payload.target)
    return GraphSnapshot(nodes=[node_out(node) for node in nodes], edges=[edge_out(edge) for edge in edges])
