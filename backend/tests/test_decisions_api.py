"""Integration tests for the Decision Intelligence API (Phase 11), against
a live Postgres, hitting the real HTTP endpoints - RBAC, the approval
lifecycle, the audit trail, and the two Phase 11 DoD scenarios end to end.
Unit-level coverage for the underlying pieces (scenario verification,
recommendation composition) lives in tests/decision/ - this file is about
the wiring, never the algorithms.
"""

import uuid

from tests.conftest import FIXTURES_DIR


def _upload(client, filename: str) -> str:
    path = FIXTURES_DIR / filename
    files = {"file": (filename, path.read_bytes(), "text/csv")}
    response = client.post("/datasets/upload", files=files)
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Authentication / RBAC
# ---------------------------------------------------------------------------


def test_unauthenticated_requests_are_rejected(unauthenticated_client):
    assert unauthenticated_client.get("/decisions").status_code == 401
    assert unauthenticated_client.post("/decisions", json={"question": "q"}).status_code == 401


def test_viewer_can_read_but_not_propose_or_approve(client, viewer_headers):
    dataset_id = _upload(client, "decision_finance_sample.csv")

    propose = client.post(
        "/decisions", json={"dataset_id": dataset_id, "question": "recommend an action"},
        headers=viewer_headers,
    )
    assert propose.status_code == 403

    listed = client.get("/decisions", headers=viewer_headers)
    assert listed.status_code == 200


def test_analyst_can_propose_but_not_approve(client, analyst_headers):
    dataset_id = _upload(client, "decision_finance_sample.csv")

    propose = client.post(
        "/decisions", json={"dataset_id": dataset_id, "question": "recommend an action"},
        headers=analyst_headers,
    )
    assert propose.status_code == 201, propose.text
    recommendation_id = propose.json()["id"]

    approve = client.post(f"/decisions/{recommendation_id}/approve", headers=analyst_headers)
    assert approve.status_code == 403


# ---------------------------------------------------------------------------
# Phase 11 DoD scenario 1: verified-relationship scenario analysis
# ---------------------------------------------------------------------------


def test_dod_scenario_1_verified_relationship_scenario_analysis(client):
    dataset_id = _upload(client, "decision_finance_sample.csv")

    response = client.post(
        "/decisions/scenario",
        json={"dataset_id": dataset_id, "question": "What happens to profit if revenue decreases by 10%?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["computed"] is True
    assert body["relationship"] == "profit = revenue - cost"
    assert "linear extrapolation" in body["note"]
    assert "not a causal or predictive model" in body["note"]


def test_scenario_endpoint_never_persists_anything(client):
    dataset_id = _upload(client, "decision_finance_sample.csv")
    client.post(
        "/decisions/scenario",
        json={"dataset_id": dataset_id, "question": "What happens to profit if revenue decreases by 10%?"},
    )
    listed = client.get("/decisions", params={"dataset_id": dataset_id})
    assert listed.json() == []


# ---------------------------------------------------------------------------
# Phase 11 DoD scenario 2: ML -> Risk -> Decision produces a pending
# recommendation, then an ADMIN approves it
# ---------------------------------------------------------------------------


def test_dod_scenario_2_forecast_and_recommend_then_approve(client):
    dataset_id = _upload(client, "ml_sales_timeseries_sample.csv")

    run_response = client.post(
        "/agents/run",
        json={
            "question": "Forecast next quarter's revenue and recommend an action if there's a risk",
            "dataset_id": dataset_id,
        },
    )
    assert run_response.status_code == 200, run_response.text
    body = run_response.json()

    assert body["status"] == "answered"
    assert body["agents_invoked"] == ["ml", "risk", "decision"]
    decision_outcome = body["agent_outcomes"][2]
    assert decision_outcome["agent"] == "decision"
    propose_outcome = decision_outcome["outcomes"][0]
    assert propose_outcome["tool"] == "propose"
    recommendation_id = propose_outcome["data"]["id"]
    assert propose_outcome["data"]["status"] == "pending"

    detail = client.get(f"/decisions/{recommendation_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["status"] == "pending"
    assert detail_body["evidence"]  # ML + Risk evidence present
    assert detail_body["confidence"] in ("low", "medium", "high")
    assert isinstance(detail_body["assumptions"], list)

    # Scenario 3: as ADMIN (the `client` fixture's default identity),
    # approve it.
    approve = client.post(f"/decisions/{recommendation_id}/approve")
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    logs = client.get("/audit-logs", params={"action": "decision.approved"})
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1


def test_double_approve_returns_409(client):
    dataset_id = _upload(client, "decision_finance_sample.csv")
    propose = client.post("/decisions", json={"dataset_id": dataset_id, "question": "recommend"})
    recommendation_id = propose.json()["id"]

    first = client.post(f"/decisions/{recommendation_id}/approve")
    assert first.status_code == 200
    second = client.post(f"/decisions/{recommendation_id}/reject")
    assert second.status_code == 409


# ---------------------------------------------------------------------------
# Scenario 4: VIEWER can view but not approve/reject, direct API 403
# ---------------------------------------------------------------------------


def test_dod_scenario_4_viewer_can_view_but_cannot_approve(client, viewer_headers):
    dataset_id = _upload(client, "decision_finance_sample.csv")
    propose = client.post("/decisions", json={"dataset_id": dataset_id, "question": "recommend"})
    recommendation_id = propose.json()["id"]

    viewer_read = client.get(f"/decisions/{recommendation_id}", headers=viewer_headers)
    assert viewer_read.status_code == 200

    viewer_approve = client.post(f"/decisions/{recommendation_id}/approve", headers=viewer_headers)
    assert viewer_approve.status_code == 403


# ---------------------------------------------------------------------------
# Graceful handling / audit
# ---------------------------------------------------------------------------


def test_unknown_dataset_id_returns_404_for_propose_and_scenario(client):
    unknown = str(uuid.uuid4())
    assert client.post("/decisions", json={"dataset_id": unknown, "question": "q"}).status_code == 404
    assert client.post("/decisions/scenario", json={"dataset_id": unknown, "question": "q"}).status_code == 404


def test_unknown_recommendation_id_returns_404(client):
    assert client.get(f"/decisions/{uuid.uuid4()}").status_code == 404
    assert client.post(f"/decisions/{uuid.uuid4()}/approve").status_code == 404


def test_proposing_a_recommendation_produces_an_audit_event(client):
    dataset_id = _upload(client, "decision_finance_sample.csv")
    client.post("/decisions", json={"dataset_id": dataset_id, "question": "recommend"})

    logs = client.get("/audit-logs", params={"action": "decision.proposed"})
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1


def test_rejecting_a_recommendation_produces_an_audit_event(client):
    dataset_id = _upload(client, "decision_finance_sample.csv")
    propose = client.post("/decisions", json={"dataset_id": dataset_id, "question": "recommend"})
    recommendation_id = propose.json()["id"]
    client.post(f"/decisions/{recommendation_id}/reject")

    logs = client.get("/audit-logs", params={"action": "decision.rejected"})
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1
