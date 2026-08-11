"""Integration tests for the KPI API, against a live Postgres.

Expected numbers below are computed by hand from
tests/fixtures/orders_sample.csv (20 rows) so these tests catch real
aggregation bugs, not just "the endpoint returns 200."
"""

from tests.conftest import FIXTURES_DIR


def _upload_orders_sample(client):
    path = FIXTURES_DIR / "orders_sample.csv"
    files = {"file": ("orders_sample.csv", path.read_bytes(), "text/csv")}
    response = client.post("/datasets/upload", files=files)
    assert response.status_code == 201
    return response.json()["id"]


def test_kpi_summary_computes_real_aggregates(client):
    dataset_id = _upload_orders_sample(client)
    summary = client.get(f"/datasets/{dataset_id}/kpis").json()

    assert set(summary["numeric_columns"]) == {"order_id", "quantity", "unit_price"}
    assert "region" in summary["suggested_breakdown_columns"]
    assert "category" in summary["suggested_breakdown_columns"]
    assert summary["suggested_trend_columns"] == ["order_date"]

    kpi_by_key = {(k["column"], k["kind"]): k["value"] for k in summary["kpis"]}
    assert kpi_by_key[("quantity", "sum")] == 65.0
    assert kpi_by_key[("quantity", "average")] == 3.25
    assert kpi_by_key[("quantity", "min")] == 1.0
    assert kpi_by_key[("quantity", "max")] == 12.0


def test_breakdown_by_region_count(client):
    dataset_id = _upload_orders_sample(client)
    response = client.get(
        f"/datasets/{dataset_id}/kpis/breakdown", params={"group_by": "region", "agg": "count"}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["total_categories"] == 4
    values_by_category = {item["category"]: item["value"] for item in body["items"]}
    assert values_by_category == {"North": 5, "South": 5, "East": 5, "West": 5}


def test_breakdown_sum_of_metric_by_category(client):
    dataset_id = _upload_orders_sample(client)
    response = client.get(
        f"/datasets/{dataset_id}/kpis/breakdown",
        params={"group_by": "category", "metric": "quantity", "agg": "sum"},
    )
    body = response.json()
    values_by_category = {item["category"]: item["value"] for item in body["items"]}

    assert values_by_category == {
        "Electronics": 16.0,
        "Furniture": 8.0,
        "Stationery": 36.0,
        "Office Supplies": 5.0,
    }


def test_trend_by_month(client):
    dataset_id = _upload_orders_sample(client)
    response = client.get(
        f"/datasets/{dataset_id}/kpis/trend",
        params={
            "date_column": "order_date",
            "metric": "quantity",
            "granularity": "month",
            "agg": "sum",
        },
    )
    assert response.status_code == 200
    points = response.json()["points"]

    assert points == [
        {"period": "2024-01-01", "value": 41.0},
        {"period": "2024-02-01", "value": 24.0},
    ]


def test_breakdown_rejects_unknown_column(client):
    dataset_id = _upload_orders_sample(client)
    response = client.get(
        f"/datasets/{dataset_id}/kpis/breakdown", params={"group_by": "nonexistent_column"}
    )
    assert response.status_code == 400


def test_breakdown_rejects_non_numeric_metric(client):
    dataset_id = _upload_orders_sample(client)
    response = client.get(
        f"/datasets/{dataset_id}/kpis/breakdown",
        params={"group_by": "region", "metric": "customer_name", "agg": "sum"},
    )
    assert response.status_code == 400


def test_trend_rejects_non_datetime_column(client):
    dataset_id = _upload_orders_sample(client)
    response = client.get(
        f"/datasets/{dataset_id}/kpis/trend",
        params={"date_column": "region", "metric": "quantity"},
    )
    assert response.status_code == 400


def test_kpis_for_nonexistent_dataset_returns_404(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/datasets/{fake_id}/kpis").status_code == 404
