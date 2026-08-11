"""Tests for GET /health.

These run against whatever DATABASE_URL is configured in backend/.env (or
the environment) - i.e. against a real Postgres, started via
infra/docker-compose.yml. This is deliberate for Phase 1: the point of this
endpoint is to prove real DB connectivity, so mocking the database would
defeat the purpose.
"""

from fastapi.testclient import TestClient


def test_health_returns_ok_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert "app_name" in body


def test_health_response_shape(client: TestClient) -> None:
    response = client.get("/health")
    body = response.json()

    assert set(body.keys()) == {"status", "app_name", "app_env", "database"}
