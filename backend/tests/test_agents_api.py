"""Integration tests for the multi-agent orchestration API (Phase 10),
against a live Postgres, hitting the real HTTP endpoints - RBAC, the audit
trail, and the DoD scenario end-to-end. Unit-level coverage for the
underlying pieces (routing, each agent's tools, the orchestrator) lives in
tests/agents/ - this file is about the wiring, never the algorithms.
"""

import uuid

from tests.conftest import FIXTURES_DIR


def _upload(client, filename: str, content_type: str = "text/csv") -> str:
    path = FIXTURES_DIR / filename
    files = {"file": (filename, path.read_bytes(), content_type)}
    response = client.post("/datasets/upload", files=files)
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Authentication / RBAC
# ---------------------------------------------------------------------------


def test_unauthenticated_requests_are_rejected(unauthenticated_client):
    assert unauthenticated_client.get("/agents").status_code == 401
    assert unauthenticated_client.post("/agents/run", json={"question": "hi"}).status_code == 401


def test_viewer_cannot_run_or_list_agents_no_agents_run_permission(client, viewer_headers):
    assert client.get("/agents", headers=viewer_headers).status_code == 403
    response = client.post(
        "/agents/run", json={"question": "What is the total quantity?"}, headers=viewer_headers
    )
    assert response.status_code == 403


def test_analyst_can_list_the_agent_catalog(client, analyst_headers):
    response = client.get("/agents", headers=analyst_headers)
    assert response.status_code == 200
    names = {a["name"] for a in response.json()}
    assert names == {"data", "analytics", "ml", "research", "risk"}


# ---------------------------------------------------------------------------
# The Phase 10 DoD scenario, end to end over HTTP
# ---------------------------------------------------------------------------


def test_the_phase_10_dod_scenario_over_http(client):
    dataset_id = _upload(client, "ml_sales_timeseries_sample.csv")

    response = client.post(
        "/agents/run",
        json={
            "question": "Forecast next quarter's revenue and flag any risk factors.",
            "dataset_id": dataset_id,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "answered"
    assert body["agents_invoked"] == ["ml", "risk"]
    assert [a["agent"] for a in body["agent_outcomes"]] == ["ml", "risk"]
    ml_outcomes = body["agent_outcomes"][0]["outcomes"]
    assert [o["tool"] for o in ml_outcomes] == ["check_suitability", "forecast"]
    assert ml_outcomes[1]["allowed"] is True
    risk_outcomes = body["agent_outcomes"][1]["outcomes"]
    assert risk_outcomes[0]["data"]["overall_severity"] in ("info", "warning", "critical")


def test_unsupported_question_returns_200_not_an_error(client):
    response = client.post("/agents/run", json={"question": "asdkjfh qpwoeiru nonsense"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "unsupported"
    assert body["agents_invoked"] == []


def test_unknown_dataset_id_returns_404(client):
    response = client.post(
        "/agents/run",
        json={"question": "forecast next quarter", "dataset_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_empty_question_is_rejected_by_request_validation(client):
    response = client.post("/agents/run", json={"question": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


def test_running_agents_produces_an_audit_event(client):
    client.post("/agents/run", json={"question": "What is the total revenue?"})

    logs = client.get("/audit-logs", params={"action": "agents.run_performed"})
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1
