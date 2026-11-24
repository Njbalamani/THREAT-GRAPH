def test_health_and_docs(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/").json()["name"] == "ThreatGraph"
    assert client.get("/openapi.json").status_code == 200


def test_login_and_me(client):
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@threatgraph.local", "password": "ChangeMe123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_invalid_login(client):
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@threatgraph.local", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401


def test_rbac_blocks_analyst_from_admin_route(client, auth_headers, unique_username):
    created = client.post(
        "/api/auth/register",
        json={
            "email": f"{unique_username}@example.test",
            "username": unique_username,
            "full_name": "Test Analyst",
            "password": "AnalystPass123!",
            "role": "analyst",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        data={"username": unique_username, "password": "AnalystPass123!"},
    )
    analyst_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    denied = client.post(
        "/api/feeds",
        json={
            "name": "Blocked Feed",
            "feed_type": "json",
            "url": "https://feed.example.test/indicators.json",
        },
        headers=analyst_headers,
    )
    assert denied.status_code == 403
