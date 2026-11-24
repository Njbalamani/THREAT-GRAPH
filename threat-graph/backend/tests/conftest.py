import os
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "threatgraph-test-secret-key"
os.environ["NEO4J_ENABLED"] = "false"
os.environ["ADMIN_EMAIL"] = "admin@threatgraph.local"
os.environ["ADMIN_PASSWORD"] = "ChangeMe123!"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.graph.factory import set_graph_store
from app.graph.networkx_store import NetworkXGraphStore
from app.main import app
from app.models import Base
from app.models.enums import UserRole
from app.models.user import User


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine, expire_on_commit=False)


@pytest.fixture
def client(session_factory, tmp_path):
    settings.model_dir = str(tmp_path / "models")
    settings.neo4j_enabled = False
    set_graph_store(NetworkXGraphStore(tmp_path / "graph.json"))

    admin = User(
        email=settings.admin_email.lower(),
        username="admin",
        full_name="Test Administrator",
        hashed_password=hash_password(settings.admin_password),
        role=UserRole.ADMIN,
    )
    session = session_factory()
    session.add(admin)
    session.commit()
    session.close()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    set_graph_store(None)


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@threatgraph.local", "password": "ChangeMe123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def unique_username():
    return f"analyst-{uuid4().hex[:8]}"
