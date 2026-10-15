def test_health_endpoint(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_search_endpoint(api_client):
    response = api_client.post(
        "/search",
        json={
            "query": "ఆకాశము",
            "top_k": 3,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["query"] == "ఆకాశము"
    assert "mode" in data
    assert "results" in data
    assert len(data["results"]) <= 3
