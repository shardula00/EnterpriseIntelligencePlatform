"""Integration tests for the knowledge graph API (Phase 9), against a live
Postgres, hitting the real HTTP endpoint - RBAC, the audit trail, and that
no standalone graph-browsing endpoint was added (see app/kg/__init__.py).
Unit-level coverage for the underlying pieces (entity/relationship
extraction, graph traversal) lives in tests/kg/ - this file is about the
wiring, never the algorithms.
"""

import uuid

from tests.conftest import FIXTURES_DIR


def _upload_orders_sample(client) -> str:
    path = FIXTURES_DIR / "orders_sample.csv"
    files = {"file": ("orders_sample.csv", path.read_bytes(), "text/csv")}
    response = client.post("/datasets/upload", files=files)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_unauthenticated_requests_are_rejected(unauthenticated_client):
    assert unauthenticated_client.post("/datasets/00000000-0000-0000-0000-000000000000/graph/build").status_code == 401


def test_viewer_cannot_build_graph_no_dataset_create_permission(client, viewer_headers):
    dataset_id = _upload_orders_sample(client)
    response = client.post(f"/datasets/{dataset_id}/graph/build", headers=viewer_headers)
    assert response.status_code == 403


def test_analyst_can_build_graph(client, analyst_headers):
    dataset_id = _upload_orders_sample(client)
    response = client.post(f"/datasets/{dataset_id}/graph/build", headers=analyst_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dataset_id"] == dataset_id
    assert body["entity_count"] > 0
    assert body["relationship_count"] == 20 * 4
    assert set(body["entity_types"]) == {"Category", "Customer", "Order", "Product", "Region"}


def test_build_graph_is_idempotent_over_http(client):
    dataset_id = _upload_orders_sample(client)
    first = client.post(f"/datasets/{dataset_id}/graph/build")
    second = client.post(f"/datasets/{dataset_id}/graph/build")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["entity_count"] == second.json()["entity_count"]


def test_unknown_dataset_returns_404(client):
    response = client.post(f"/datasets/{uuid.uuid4()}/graph/build")
    assert response.status_code == 404


def test_building_graph_produces_an_audit_event(client):
    dataset_id = _upload_orders_sample(client)
    client.post(f"/datasets/{dataset_id}/graph/build")

    logs = client.get("/audit-logs", params={"action": "kg.graph_built"})
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1


def test_no_standalone_graph_browsing_endpoint_exists(client):
    dataset_id = _upload_orders_sample(client)
    client.post(f"/datasets/{dataset_id}/graph/build")

    # Per the approved Phase 9 design: graph evidence only ever surfaces
    # through POST /rag/query in hybrid mode - there is deliberately no
    # GET endpoint to browse entities/relationships directly.
    response = client.get(f"/datasets/{dataset_id}/graph/entities")
    assert response.status_code in (404, 405)
