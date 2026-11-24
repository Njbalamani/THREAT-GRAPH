def test_full_platform_flow(client, auth_headers):
    seeded = client.post("/api/system/seed-samples", headers=auth_headers)
    assert seeded.status_code == 200, seeded.text
    payload = seeded.json()
    assert payload["seeded_files"] >= 4
    assert all(result["status"] == "completed" for result in payload["results"])

    summary = client.get("/api/dashboard/summary", headers=auth_headers)
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert data["totals"]["indicators"] > 0
    assert data["totals"]["relationships"] > 0
    assert data["graph"]["observed_edges"] > 0

    snapshot = client.get("/api/graph/snapshot", headers=auth_headers)
    assert snapshot.status_code == 200
    graph = snapshot.json()
    assert len(graph["nodes"]) > 0
    assert len(graph["edges"]) > 0
    assert any(edge["provenance"] == "observed" for edge in graph["edges"])

    analysis = client.post("/api/analytics/graph/analyze?persist=true", headers=auth_headers)
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["node_count"] > 0

    training = client.post("/api/analytics/model/train", headers=auth_headers)
    assert training.status_code == 200, training.text
    assert training.json()["training_samples"] > 1

    predictions = client.get("/api/analytics/predictions", headers=auth_headers)
    assert predictions.status_code == 200, predictions.text
    predicted = predictions.json()
    assert len(predicted) > 0
    assert all(item["prediction_only"] is True for item in predicted)
    assert all(item["confirmed"] is False for item in predicted)
    assert all(item["explanation"] for item in predicted)

    indicators = client.get("/api/indicators?limit=5", headers=auth_headers).json()
    assert indicators
    case_response = client.post(
        "/api/investigations",
        json={
            "title": "Sample credential campaign",
            "description": "Integrated investigation flow",
            "priority": "high",
        },
        headers=auth_headers,
    )
    assert case_response.status_code == 201, case_response.text
    case_id = case_response.json()["investigation"]["id"]

    associated = client.post(
        f"/api/investigations/{case_id}/indicators/{indicators[0]['id']}",
        headers=auth_headers,
    )
    assert associated.status_code == 200
    assert len(associated.json()["indicators"]) == 1

    note = client.post(
        f"/api/investigations/{case_id}/notes",
        json={"content": "Analyst review pending: correlate with sandbox telemetry."},
        headers=auth_headers,
    )
    assert note.status_code == 201

    timeline = client.get(f"/api/investigations/{case_id}/timeline", headers=auth_headers)
    assert timeline.status_code == 200
    assert any(item["kind"] == "note" for item in timeline.json())

    pdf = client.post(
        "/api/reports/pdf",
        json={"title": "ThreatGraph Validation Report", "include_predictions": True},
        headers=auth_headers,
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    assert "application/pdf" in pdf.headers["content-type"]

    csv = client.get("/api/exports/indicators.csv", headers=auth_headers)
    assert csv.status_code == 200
    assert "type,value,severity" in csv.text

    graph_json = client.get("/api/exports/graph.json", headers=auth_headers)
    assert graph_json.status_code == 200
    assert graph_json.json()["backend"] == "networkx"
