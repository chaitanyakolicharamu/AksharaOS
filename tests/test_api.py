from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_search_endpoint():
    response = client.post(
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
