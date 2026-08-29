from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_create_and_read_task() -> None:
    with TestClient(app) as client:
        created = client.post("/api/tasks", json={"source_name": "sample.mp4"})
        assert created.status_code == 201
        task = created.json()

        fetched = client.get(f"/api/tasks/{task['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["source_name"] == "sample.mp4"
