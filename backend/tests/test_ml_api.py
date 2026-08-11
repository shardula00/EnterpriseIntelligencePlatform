"""Integration tests for the ML API (Phase 5), against a live Postgres.

Uses the 4 dedicated synthetic ML fixtures (tests/fixtures/ml_*.csv, see
tests/conftest.py's cleanup fixtures for how the datasets/runs/artifacts
they create get cleaned up) - each one built for exactly one task, so
suitability results are asserted for real, not just "200 OK."
"""

from tests.conftest import FIXTURES_DIR


def _upload(client, filename: str) -> str:
    path = FIXTURES_DIR / filename
    files = {"file": (filename, path.read_bytes(), "text/csv")}
    response = client.post("/datasets/upload", files=files)
    assert response.status_code == 201
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Suitability
# ---------------------------------------------------------------------------


def test_suitability_for_churn_dataset(client):
    dataset_id = _upload(client, "ml_churn_sample.csv")
    body = client.get(f"/datasets/{dataset_id}/ml/suitability").json()
    by_task = {t["task_type"]: t for t in body["tasks"]}

    assert by_task["classification"]["suitable"] is True
    assert "churned" in by_task["classification"]["suggested_target_columns"]
    assert by_task["forecasting"]["suitable"] is False
    assert any("no datetime column was detected" in r for r in by_task["forecasting"]["reasons"])


def test_suitability_for_sales_timeseries_dataset(client):
    dataset_id = _upload(client, "ml_sales_timeseries_sample.csv")
    body = client.get(f"/datasets/{dataset_id}/ml/suitability").json()
    by_task = {t["task_type"]: t for t in body["tasks"]}

    assert by_task["forecasting"]["suitable"] is True
    assert by_task["forecasting"]["suggested_datetime_columns"] == ["order_date"]
    assert by_task["classification"]["suitable"] is False
    assert by_task["segmentation"]["suitable"] is False  # only 1 numeric column


def test_suitability_for_segmentation_dataset(client):
    dataset_id = _upload(client, "ml_customers_segmentation_sample.csv")
    body = client.get(f"/datasets/{dataset_id}/ml/suitability").json()
    by_task = {t["task_type"]: t for t in body["tasks"]}

    assert by_task["segmentation"]["suitable"] is True
    assert len(by_task["segmentation"]["suggested_feature_columns"]) == 4
    assert by_task["classification"]["suitable"] is False


def test_suitability_for_anomaly_dataset(client):
    dataset_id = _upload(client, "ml_transactions_anomaly_sample.csv")
    body = client.get(f"/datasets/{dataset_id}/ml/suitability").json()
    by_task = {t["task_type"]: t for t in body["tasks"]}

    assert by_task["anomaly_detection"]["suitable"] is True
    assert by_task["forecasting"]["suitable"] is False


def test_suitability_for_nonexistent_dataset_returns_404(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/datasets/{fake_id}/ml/suitability").status_code == 404


# ---------------------------------------------------------------------------
# Train: classification
# ---------------------------------------------------------------------------


def test_train_classification_end_to_end(client):
    dataset_id = _upload(client, "ml_churn_sample.csv")
    response = client.post(
        "/ml/train/classification",
        json={"dataset_id": dataset_id, "target_column": "churned"},
    )
    assert response.status_code == 201
    body = response.json()

    assert body["run"]["task_type"] == "classification"
    assert body["run"]["status"] == "completed"
    results = body["results"]
    assert results["primary_metric"] == "roc_auc"
    assert results["metrics"]["roc_auc"] > 0.6
    assert len(results["candidate_models"]) == 3
    assert results["confusion_matrix"]["labels"] == ["False", "True"]


def test_train_classification_rejects_bad_target_column(client):
    dataset_id = _upload(client, "ml_churn_sample.csv")
    response = client.post(
        "/ml/train/classification",
        json={"dataset_id": dataset_id, "target_column": "monthly_charges"},  # not binary
    )
    assert response.status_code == 400


def test_train_classification_rejects_unknown_dataset(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        "/ml/train/classification", json={"dataset_id": fake_id, "target_column": "churned"}
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Train: forecasting
# ---------------------------------------------------------------------------


def test_train_forecasting_end_to_end(client):
    dataset_id = _upload(client, "ml_sales_timeseries_sample.csv")
    response = client.post(
        "/ml/train/forecasting",
        json={
            "dataset_id": dataset_id,
            "datetime_column": "order_date",
            "target_column": "sales_amount",
            "horizon": 14,
        },
    )
    assert response.status_code == 201
    results = response.json()["results"]
    assert results["horizon"] == 14
    assert len(results["forecast"]) == 14
    assert len(results["historical"]) == 400


def test_train_forecasting_rejects_non_datetime_column(client):
    dataset_id = _upload(client, "ml_sales_timeseries_sample.csv")
    response = client.post(
        "/ml/train/forecasting",
        json={
            "dataset_id": dataset_id,
            "datetime_column": "sales_amount",
            "target_column": "sales_amount",
        },
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Train: segmentation
# ---------------------------------------------------------------------------


def test_train_segmentation_end_to_end(client):
    dataset_id = _upload(client, "ml_customers_segmentation_sample.csv")
    response = client.post(
        "/ml/train/segmentation",
        json={"dataset_id": dataset_id, "n_clusters": 4},
    )
    assert response.status_code == 201
    results = response.json()["results"]
    assert results["n_clusters"] == 4
    assert len(results["cluster_profiles"]) == 4
    assert 0.0 <= results["silhouette_score"] <= 1.0


def test_train_segmentation_rejects_n_clusters_out_of_schema_range(client):
    dataset_id = _upload(client, "ml_customers_segmentation_sample.csv")
    response = client.post(
        "/ml/train/segmentation", json={"dataset_id": dataset_id, "n_clusters": 20}
    )
    assert response.status_code == 422  # outside Field(ge=2, le=8) - a schema-level rejection


# ---------------------------------------------------------------------------
# Train: anomaly detection
# ---------------------------------------------------------------------------


def test_train_anomaly_detection_end_to_end(client):
    dataset_id = _upload(client, "ml_transactions_anomaly_sample.csv")
    response = client.post(
        "/ml/train/anomaly-detection",
        json={"dataset_id": dataset_id, "contamination": 0.05},
    )
    assert response.status_code == 201
    results = response.json()["results"]
    assert results["contamination"] == 0.05
    assert results["anomaly_count"] > 0
    assert len(results["anomalous_records"]) == results["anomaly_count"]


# ---------------------------------------------------------------------------
# Run history + results + predict
# ---------------------------------------------------------------------------


def test_list_and_get_run_after_training(client):
    dataset_id = _upload(client, "ml_churn_sample.csv")
    train_response = client.post(
        "/ml/train/classification", json={"dataset_id": dataset_id, "target_column": "churned"}
    )
    run_id = train_response.json()["run"]["id"]

    list_response = client.get("/ml/runs", params={"dataset_id": dataset_id})
    assert list_response.status_code == 200
    assert any(r["id"] == run_id for r in list_response.json())

    get_response = client.get(f"/ml/runs/{run_id}")
    assert get_response.status_code == 200
    assert get_response.json()["run"]["id"] == run_id


def test_get_nonexistent_run_returns_404(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/ml/runs/{fake_id}").status_code == 404


def test_predict_from_a_trained_classification_run(client):
    dataset_id = _upload(client, "ml_churn_sample.csv")
    train_response = client.post(
        "/ml/train/classification", json={"dataset_id": dataset_id, "target_column": "churned"}
    )
    run_id = train_response.json()["run"]["id"]

    predict_response = client.post(f"/ml/runs/{run_id}/predict", json={})
    assert predict_response.status_code == 200
    body = predict_response.json()
    assert body["task_type"] == "classification"
    assert body["summary"]["row_count"] == 500
    assert len(body["predictions"]) == 500


def test_predict_from_a_trained_forecast_run_with_custom_horizon(client):
    dataset_id = _upload(client, "ml_sales_timeseries_sample.csv")
    train_response = client.post(
        "/ml/train/forecasting",
        json={
            "dataset_id": dataset_id,
            "datetime_column": "order_date",
            "target_column": "sales_amount",
            "horizon": 14,
        },
    )
    run_id = train_response.json()["run"]["id"]

    predict_response = client.post(f"/ml/runs/{run_id}/predict", json={"horizon": 5})
    assert predict_response.status_code == 200
    body = predict_response.json()
    assert len(body["predictions"]) == 5
    assert body["summary"]["horizon"] == 5


def test_predict_from_nonexistent_run_returns_404(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/ml/runs/{fake_id}/predict", json={}).status_code == 404


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_unauthenticated_request_is_rejected(unauthenticated_client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = unauthenticated_client.get(f"/datasets/{fake_id}/ml/suitability")
    assert response.status_code == 401


def test_viewer_can_read_but_not_train(client, viewer_headers):
    dataset_id = _upload(client, "ml_churn_sample.csv")

    read_response = client.get(f"/datasets/{dataset_id}/ml/suitability", headers=viewer_headers)
    assert read_response.status_code == 200

    train_response = client.post(
        "/ml/train/classification",
        json={"dataset_id": dataset_id, "target_column": "churned"},
        headers=viewer_headers,
    )
    assert train_response.status_code == 403


def test_analyst_can_train_and_predict(client, analyst_headers):
    dataset_id = _upload(client, "ml_churn_sample.csv")

    train_response = client.post(
        "/ml/train/classification",
        json={"dataset_id": dataset_id, "target_column": "churned"},
        headers=analyst_headers,
    )
    assert train_response.status_code == 201
    run_id = train_response.json()["run"]["id"]

    predict_response = client.post(f"/ml/runs/{run_id}/predict", json={}, headers=analyst_headers)
    assert predict_response.status_code == 200
