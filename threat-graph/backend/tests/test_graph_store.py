from app.graph.networkx_store import NetworkXGraphStore
from app.graph.types import GraphEdge, GraphNode


def test_graph_store_persists_observed_and_inferred_edges(tmp_path):
    path = tmp_path / "graph.json"
    store = NetworkXGraphStore(path)
    store.upsert_many(
        [
            GraphNode(key="indicator:a", type="indicator", label="192.0.2.41"),
            GraphNode(key="event:1", type="event", label="Auth failure"),
            GraphNode(key="domain:b", type="domain", label="login-portal.example"),
        ],
        [
            GraphEdge(
                source="indicator:a",
                target="event:1",
                relationship="source_ip_linked",
                provenance="observed",
                confidence=0.95,
            ),
            GraphEdge(
                source="indicator:a",
                target="domain:b",
                relationship="shared_domain",
                provenance="inferred",
                confidence=0.45,
            ),
        ],
    )

    stats = store.stats()
    assert stats["node_count"] == 3
    assert stats["edge_count"] == 2
    assert stats["observed_edges"] == 1
    assert stats["inferred_edges"] == 1

    reloaded = NetworkXGraphStore(path)
    nodes, edges = reloaded.get_snapshot()
    assert len(nodes) == 3
    assert {edge.provenance for edge in edges} == {"observed", "inferred"}

    path_nodes, path_edges = reloaded.shortest_path("event:1", "domain:b")
    assert [node.key for node in path_nodes] == ["event:1", "indicator:a", "domain:b"]
    assert len(path_edges) == 2
