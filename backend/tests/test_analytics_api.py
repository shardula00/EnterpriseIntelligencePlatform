"""Integration tests for the natural-language analytics API (Phase 8),
against a live Postgres, hitting the real HTTP endpoints - RBAC,
generated-SQL presence, graceful handling of unsupported questions/unknown
datasets, and the audit trail. Unit-level coverage for the underlying
pieces (parsing, query building, SQL validation) lives in tests/analytics/
- this file is about the wiring, never the algorithms.
"""

import uuid

from tests.conftest import FIXTURES_DIR


def _upload_orders_sample(client) -> str:
    path = FIXTURES_DIR / "orders_sample.csv"
    files = {"file": ("orders_sample.csv", path.read_bytes(), "text/csv")}
    response = client.post("/datasets/upload", files=files)
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Authentication / RBAC
# ---------------------------------------------------------------------------


def test_unauthenticated_requests_are_rejected(unauthenticated_client):
    assert unauthenticated_client.post("/analytics/query", json={}).status_code == 401
    assert unauthenticated_client.get("/analytics/queries").status_code == 401


def test_viewer_can_read_history_but_not_ask_a_question(client, viewer_headers):
    dataset_id = _upload_orders_sample(client)

    ask_response = client.post(
        "/analytics/query",
        json={"dataset_id": dataset_id, "question": "total quantity"},
        headers=viewer_headers,
    )
    assert ask_response.status_code == 403

    list_response = client.get("/analytics/queries", headers=viewer_headers)
    assert list_response.status_code == 200


def test_analyst_can_ask_a_question(client, analyst_headers):
    dataset_id = _upload_orders_sample(client)

    response = client.post(
        "/analytics/query",
        json={"dataset_id": dataset_id, "question": "total quantity"},
        headers=analyst_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "answered"


# ---------------------------------------------------------------------------
# The core flow: dataset -> question -> generated SQL -> executed -> result
# ---------------------------------------------------------------------------


def test_total_question_returns_a_grounded_result_with_generated_sql(client):
    dataset_id = _upload_orders_sample(client)

    response = client.post(
        "/analytics/query", json={"dataset_id": dataset_id, "question": "What is the total quantity?"}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "answered"
    assert body["dataset_id"] == dataset_id
    assert body["generated_sql"].upper().startswith("SELECT")
    assert body["row_count"] == 1
    assert body["rows"][0]["quantity"] == 65


def test_breakdown_question_returns_a_readable_table(client):
    dataset_id = _upload_orders_sample(client)

    response = client.post(
        "/analytics/query",
        json={"dataset_id": dataset_id, "question": "Show total quantity by region."},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "answered"
    assert body["row_count"] == 4
    assert set(body["columns"]) == {"region", "quantity"}


def test_which_category_question_returns_top_ranked_row(client):
    dataset_id = _upload_orders_sample(client)

    response = client.post(
        "/analytics/query",
        json={"dataset_id": dataset_id, "question": "Which region has the highest quantity?"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["row_count"] == 1


def test_how_many_rows_question_returns_the_real_count_via_http(client):
    # Regression for the "total" + "count" missing-FROM-clause bug (bare
    # func.count() with no select_from(table) rendered with no FROM clause
    # at all, which sql_guard.py correctly rejected as status="error").
    # orders_sample.csv has exactly 20 data rows.
    dataset_id = _upload_orders_sample(client)

    response = client.post(
        "/analytics/query",
        json={"dataset_id": dataset_id, "question": "How many rows are in this dataset?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "answered"
    assert body["generated_sql"] is not None
    assert "FROM" in body["generated_sql"].upper()
    assert body["row_count"] == 1
    assert body["rows"][0]["count"] == 20


# ---------------------------------------------------------------------------
# Graceful handling: unsupported questions, unknown datasets, bad input
# ---------------------------------------------------------------------------


def test_unsupported_question_returns_200_not_an_error(client):
    dataset_id = _upload_orders_sample(client)

    response = client.post(
        "/analytics/query",
        json={"dataset_id": dataset_id, "question": "What is the weather like today?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "unsupported"
    assert body["generated_sql"] is None
    assert body["rows"] == []


def test_unknown_dataset_id_returns_404(client):
    response = client.post(
        "/analytics/query",
        json={"dataset_id": str(uuid.uuid4()), "question": "total quantity"},
    )
    assert response.status_code == 404


def test_empty_question_is_rejected_by_request_validation(client):
    dataset_id = _upload_orders_sample(client)
    response = client.post("/analytics/query", json={"dataset_id": dataset_id, "question": ""})
    assert response.status_code == 422


def test_malformed_dataset_id_is_rejected_by_request_validation(client):
    response = client.post(
        "/analytics/query", json={"dataset_id": "not-a-uuid", "question": "total quantity"}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# History + audit trail
# ---------------------------------------------------------------------------


def test_query_appears_in_history_and_is_individually_fetchable(client):
    dataset_id = _upload_orders_sample(client)
    asked = client.post(
        "/analytics/query", json={"dataset_id": dataset_id, "question": "total quantity"}
    ).json()

    history = client.get("/analytics/queries", params={"dataset_id": dataset_id})
    assert history.status_code == 200
    assert any(q["id"] == asked["id"] for q in history.json())

    detail = client.get(f"/analytics/queries/{asked['id']}")
    assert detail.status_code == 200
    assert detail.json()["question"] == "total quantity"


def test_unknown_query_id_returns_404(client):
    response = client.get(f"/analytics/queries/{uuid.uuid4()}")
    assert response.status_code == 404


def test_asking_a_question_produces_an_audit_event(client):
    dataset_id = _upload_orders_sample(client)
    client.post("/analytics/query", json={"dataset_id": dataset_id, "question": "total quantity"})

    logs = client.get("/audit-logs", params={"action": "analytics.query_performed"})
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1
