"""Integration tests for the MLOps API (Phase 6), against a live Postgres -
covers the full register -> promote -> drift/monitor acceptance flow, plus
permission enforcement and audit events, hitting the real HTTP endpoints
(never the service layer directly - that's tests/mlops/test_*.py's job).
"""

from tests.conftest import FIXTURES_DIR


def _upload(client, filename: str, dataset_name: str | None = None) -> str:
    path = FIXTURES_DIR / filename
    files = {"file": (filename, path.read_bytes(), "text/csv")}
    data = {"dataset_name": dataset_name} if dataset_name else {}
    response = client.post("/datasets/upload", files=files, data=data)
    assert response.status_code == 201
    return response.json()["id"]


def _train_classification(client, dataset_id: str, seed: int) -> str:
    response = client.post(
        "/ml/train/classification",
        json={"dataset_id": dataset_id, "target_column": "churned", "random_seed": seed},
    )
    assert response.status_code == 201
    return response.json()["run"]["id"]


def _promote(client, version_id: str, target_status: str, headers=None):
    kwargs = {"json": {"target_status": target_status}}
    if headers is not None:
        kwargs["headers"] = headers
    return client.post(f"/mlops/model-versions/{version_id}/promote", **kwargs)


def _register(client, run_id: str) -> dict:
    response = client.post("/mlops/model-versions", json={"ml_run_id": run_id})
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# Full acceptance flow: train -> register -> promote -> drift -> monitor
# ---------------------------------------------------------------------------


def test_full_registry_and_monitoring_flow(client):
    dataset_id = _upload(client, "ml_churn_sample.csv", "mlops-flow")
    run_a = _train_classification(client, dataset_id, seed=1)
    run_b = _train_classification(client, dataset_id, seed=2)

    version_a = _register(client, run_a)
    version_b = _register(client, run_b)
    assert version_a["version_number"] == 1
    assert version_b["version_number"] == 2
    assert version_a["status"] == "candidate"

    # A -> staging -> production
    r = _promote(client, version_a["id"], "staging")
    assert r.status_code == 200 and r.json()["status"] == "staging"
    r = _promote(client, version_a["id"], "production")
    assert r.status_code == 200 and r.json()["status"] == "production"

    # B -> staging -> production: A should auto-archive, both remain inspectable.
    _promote(client, version_b["id"], "staging")
    r = _promote(client, version_b["id"], "production")
    assert r.status_code == 200 and r.json()["status"] == "production"

    a_detail = client.get(f"/mlops/model-versions/{version_a['id']}").json()
    assert a_detail["version"]["status"] == "archived"
    assert a_detail["run"]["run"]["id"] == run_a

    listed = client.get("/mlops/model-versions", params={"dataset_id": dataset_id}).json()
    assert {v["id"] for v in listed} == {version_a["id"], version_b["id"]}

    # Drift check against a severely shifted dataset -> real drift detected.
    shifted_id = _upload(client, "ml_churn_monitoring_severe_drift.csv", "mlops-flow-shifted")
    drift_response = client.post(
        f"/mlops/model-versions/{version_b['id']}/drift-check", json={"dataset_id": shifted_id}
    )
    assert drift_response.status_code == 200
    drift_body = drift_response.json()
    assert drift_body["overall_status"] == "drift"
    assert drift_body["drifted_feature_count"] > 0
    assert len(drift_body["features"]) == drift_body["total_features_checked"]

    # Performance check against the degraded fixture -> real degradation detected.
    degraded_id = _upload(client, "ml_churn_monitoring_degraded.csv", "mlops-flow-degraded")
    perf_response = client.post(
        f"/mlops/model-versions/{version_b['id']}/performance-check",
        json={"dataset_id": degraded_id},
    )
    assert perf_response.status_code == 200
    perf_body = perf_response.json()
    assert perf_body["ground_truth_available"] is True
    assert perf_body["status"] == "degraded"

    # Both checks are visible as monitoring events/alerts.
    events_response = client.get(
        "/mlops/monitoring-events", params={"model_version_id": version_b["id"]}
    )
    events = events_response.json()
    assert len(events) == 2
    event_types = {e["event_type"] for e in events}
    assert event_types == {"drift", "performance_monitoring"}
    assert any(e["severity"] == "critical" for e in events)

    # And auditable: both actions produced a real audit_logs row.
    audit = client.get(
        "/audit-logs", params={"resource_type": "model_version", "action": "mlops.drift_check_run"}
    ).json()
    assert audit["total"] >= 1


def test_registering_a_stable_dataset_against_itself_reports_no_drift(client):
    dataset_id = _upload(client, "ml_churn_sample.csv", "mlops-stable-check")
    run_id = _train_classification(client, dataset_id, seed=1)
    version = _register(client, run_id)

    stable_id = _upload(client, "ml_churn_monitoring_stable.csv", "mlops-stable-comparison")
    response = client.post(
        f"/mlops/model-versions/{version['id']}/drift-check", json={"dataset_id": stable_id}
    )
    assert response.status_code == 200
    assert response.json()["overall_status"] == "stable"


# ---------------------------------------------------------------------------
# Validation / error paths
# ---------------------------------------------------------------------------


def test_register_rejects_the_same_run_twice(client):
    dataset_id = _upload(client, "ml_churn_sample.csv", "mlops-dup")
    run_id = _train_classification(client, dataset_id, seed=1)
    _register(client, run_id)
    response = client.post("/mlops/model-versions", json={"ml_run_id": run_id})
    assert response.status_code == 409


def test_register_rejects_unknown_run(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post("/mlops/model-versions", json={"ml_run_id": fake_id})
    assert response.status_code == 404


def test_promote_rejects_skipping_staging(client):
    dataset_id = _upload(client, "ml_churn_sample.csv", "mlops-skip-staging")
    run_id = _train_classification(client, dataset_id, seed=1)
    version = _register(client, run_id)
    response = _promote(client, version["id"], "production")
    assert response.status_code == 400


def test_archive_then_archive_again_is_rejected(client):
    dataset_id = _upload(client, "ml_churn_sample.csv", "mlops-double-archive")
    run_id = _train_classification(client, dataset_id, seed=1)
    version = _register(client, run_id)
    assert client.post(f"/mlops/model-versions/{version['id']}/archive").status_code == 200
    assert client.post(f"/mlops/model-versions/{version['id']}/archive").status_code == 400


def test_get_unknown_model_version_returns_404(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/mlops/model-versions/{fake_id}").status_code == 404


def test_performance_check_rejects_dataset_missing_target_column(client):
    dataset_id = _upload(client, "ml_churn_sample.csv", "mlops-missing-target")
    run_id = _train_classification(client, dataset_id, seed=1)
    version = _register(client, run_id)

    # ml_sales_timeseries_sample.csv has no "churned" column at all.
    other_id = _upload(client, "ml_sales_timeseries_sample.csv", "mlops-wrong-dataset")
    response = client.post(
        f"/mlops/model-versions/{version['id']}/performance-check", json={"dataset_id": other_id}
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_unauthenticated_request_is_rejected(unauthenticated_client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert unauthenticated_client.get(f"/mlops/model-versions/{fake_id}").status_code == 401


def test_viewer_can_read_but_not_evaluate_or_promote(client, viewer_headers):
    dataset_id = _upload(client, "ml_churn_sample.csv", "mlops-viewer")
    run_id = _train_classification(client, dataset_id, seed=1)
    version = _register(client, run_id)

    assert client.get("/mlops/model-versions", headers=viewer_headers).status_code == 200
    version_url = f"/mlops/model-versions/{version['id']}"
    assert client.get(version_url, headers=viewer_headers).status_code == 200
    assert client.get("/mlops/monitoring-events", headers=viewer_headers).status_code == 200

    register_response = client.post(
        "/mlops/model-versions", json={"ml_run_id": run_id}, headers=viewer_headers
    )
    assert register_response.status_code == 403

    promote_response = _promote(client, version["id"], "staging", headers=viewer_headers)
    assert promote_response.status_code == 403


def test_analyst_can_register_and_evaluate_but_not_promote(client, analyst_headers):
    dataset_id = _upload(client, "ml_churn_sample.csv", "mlops-analyst")
    run_id = _train_classification(client, dataset_id, seed=1)

    register_response = client.post(
        "/mlops/model-versions", json={"ml_run_id": run_id}, headers=analyst_headers
    )
    assert register_response.status_code == 201
    version = register_response.json()

    stable_id = _upload(client, "ml_churn_monitoring_stable.csv", "mlops-analyst-drift")
    drift_response = client.post(
        f"/mlops/model-versions/{version['id']}/drift-check",
        json={"dataset_id": stable_id},
        headers=analyst_headers,
    )
    assert drift_response.status_code == 200

    promote_response = client.post(
        f"/mlops/model-versions/{version['id']}/promote",
        json={"target_status": "staging"},
        headers=analyst_headers,
    )
    assert promote_response.status_code == 403


def test_admin_can_promote(client, admin_headers):
    dataset_id = _upload(client, "ml_churn_sample.csv", "mlops-admin-promote")
    run_id = _train_classification(client, dataset_id, seed=1)
    version = _register(client, run_id)

    response = client.post(
        f"/mlops/model-versions/{version['id']}/promote",
        json={"target_status": "staging"},
        headers=admin_headers,
    )
    assert response.status_code == 200
