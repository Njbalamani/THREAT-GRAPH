from __future__ import annotations

import logging

from app.core.config import settings
from app.graph.base import GraphStore
from app.graph.neo4j_store import Neo4jGraphStore
from app.graph.networkx_store import NetworkXGraphStore

logger = logging.getLogger(__name__)
_graph_store: GraphStore | None = None


def get_graph_store() -> GraphStore:
    global _graph_store
    if _graph_store is not None:
        return _graph_store

    if settings.neo4j_enabled:
        try:
            store = Neo4jGraphStore(
                settings.neo4j_uri,
                settings.neo4j_user,
                settings.neo4j_password,
                settings.neo4j_database,
            )
            store.verify()
            _graph_store = store
            logger.info("Neo4j graph store connected at %s", settings.neo4j_uri)
            return _graph_store
        except Exception as exc:
            logger.warning("Neo4j unavailable (%s); using local NetworkX graph store", exc)

    _graph_store = NetworkXGraphStore(settings.graph_path)
    return _graph_store


def set_graph_store(store: GraphStore | None) -> None:
    global _graph_store
    _graph_store = store


def reset_graph_store() -> None:
    global _graph_store
    if _graph_store is not None and hasattr(_graph_store, "close"):
        _graph_store.close()
    _graph_store = None
