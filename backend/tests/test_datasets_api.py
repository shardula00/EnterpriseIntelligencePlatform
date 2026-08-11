"""Integration tests for the dataset ingestion API.

These run against a live Postgres (see tests/conftest.py) and exercise the
full pipeline for real: an uploaded fixture file actually becomes a
queryable table in the `ingested` schema, not a mock.
"""

from sqlalchemy import text

from tests.conftest import FIXTURES_DIR


def _upload(client, filename: str, content_type: str, dataset_name: str | None = None):
    path = FIXTURES_DIR / filename
    files = {"file": (filename, path.read_bytes(), content_type)}
    data = {"dataset_name": dataset_name} if dataset_name else {}
    return client.post("/datasets/upload", files=files, data=data)


# ---------------------------------------------------------------------------
# Happy path: same semantic dataset in three formats
# ---------------------------------------------------------------------------


def test_upload_csv_creates_a_queryable_table(client, db_session):
    response = _upload(client, "orders_sample.csv", "text/csv")
    assert response.status_code == 201
    body = response.json()

    assert body["row_count"] == 20
    assert body["column_count"] == 9
    assert body["quality_score"] == 100.0
    assert body["file_type"] == "csv"
    assert body["status"] == "ready"

    table_name = body["storage_table_name"]
    count = db_session.execute(text(f"SELECT COUNT(*) FROM ingested.{table_name}")).scalar()
    assert count == 20


def test_upload_xlsx_matches_csv_row_count(client):
    xlsx_content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response = _upload(client, "orders_sample.xlsx", xlsx_content_type)
    assert response.status_code == 201
    body = response.json()
    assert body["row_count"] == 20
    assert body["file_type"] == "xlsx"


def test_upload_json_matches_csv_row_count(client):
    response = _upload(client, "orders_sample.json", "application/json")
    assert response.status_code == 201
    body = response.json()
    assert body["row_count"] == 20
    assert body["file_type"] == "json"


def test_uploaded_columns_have_expected_detected_types(client):
    response = _upload(client, "orders_sample.csv", "text/csv")
    dataset_id = response.json()["id"]

    columns = client.get(f"/datasets/{dataset_id}/columns").json()
    types_by_name = {c["column_name"]: c["detected_type"] for c in columns}

    assert types_by_name["order_id"] == "integer"
    assert types_by_name["quantity"] == "integer"
    assert types_by_name["unit_price"] == "float"
    assert types_by_name["order_date"] == "datetime"
    assert types_by_name["is_priority"] == "boolean"
    assert types_by_name["customer_name"] == "text"


def test_dataset_name_defaults_to_filename_stem(client):
    response = _upload(client, "orders_sample.csv", "text/csv")
    assert response.json()["name"] == "orders_sample"


def test_dataset_name_can_be_overridden(client):
    response = _upload(client, "orders_sample.csv", "text/csv", dataset_name="Q1 Orders")
    assert response.json()["name"] == "Q1 Orders"


def test_preview_returns_real_rows_from_the_table(client):
    response = _upload(client, "orders_sample.csv", "text/csv")
    dataset_id = response.json()["id"]

    preview = client.get(f"/datasets/{dataset_id}/preview", params={"limit": 5}).json()
    assert len(preview["rows"]) == 5
    assert preview["rows"][0]["customer_name"] == "Alice Johnson"
    assert preview["rows"][0]["order_id"] == 1
    assert "_row_id" not in preview["rows"][0]


# ---------------------------------------------------------------------------
# Quality / validation
# ---------------------------------------------------------------------------


def test_messy_dataset_flags_expected_quality_issues(client):
    response = _upload(client, "messy_sample.csv", "text/csv")
    assert response.status_code == 201
    body = response.json()

    assert body["quality_score"] == 64.5

    quality = client.get(f"/datasets/{body['id']}/quality").json()
    rules = {issue["rule"] for issue in quality["issues"]}
    assert rules == {"empty_column", "high_null_rate", "duplicate_rows", "duplicate_header"}


def test_clean_dataset_has_no_quality_issues(client):
    response = _upload(client, "orders_sample.csv", "text/csv")
    quality = client.get(f"/datasets/{response.json()['id']}/quality").json()
    assert quality["issues"] == []
    assert quality["quality_score"] == 100.0


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


def test_lineage_records_every_pipeline_step_in_order(client):
    response = _upload(client, "orders_sample.csv", "text/csv")
    dataset_id = response.json()["id"]

    lineage = client.get(f"/datasets/{dataset_id}/lineage").json()
    steps = [event["step"] for event in lineage["events"]]

    assert steps == [
        "upload_received",
        "validated",
        "schema_detected",
        "transformed",
        "profiled",
        "quality_scored",
        "loaded",
    ]
    assert all(event["status"] == "success" for event in lineage["events"])


# ---------------------------------------------------------------------------
# Listing, deletion
# ---------------------------------------------------------------------------


def test_uploaded_dataset_appears_in_list(client):
    response = _upload(client, "orders_sample.csv", "text/csv")
    dataset_id = response.json()["id"]

    listing = client.get("/datasets").json()
    assert any(d["id"] == dataset_id for d in listing)


def test_delete_dataset_removes_metadata_and_physical_table(client, db_session):
    response = _upload(client, "orders_sample.csv", "text/csv")
    dataset_id = response.json()["id"]
    table_name = response.json()["storage_table_name"]

    delete_response = client.delete(f"/datasets/{dataset_id}")
    assert delete_response.status_code == 204

    assert client.get(f"/datasets/{dataset_id}").status_code == 404

    table_exists = db_session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'ingested' AND table_name = :name)"
        ),
        {"name": table_name},
    ).scalar()
    assert table_exists is False


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_upload_unsupported_extension_returns_400(client):
    response = client.post(
        "/datasets/upload", files={"file": ("notes.txt", b"hello world", "text/plain")}
    )
    assert response.status_code == 400


def test_upload_empty_file_returns_400(client):
    response = client.post("/datasets/upload", files={"file": ("empty.csv", b"", "text/csv")})
    assert response.status_code == 400


def test_upload_header_only_csv_returns_400(client):
    response = client.post(
        "/datasets/upload", files={"file": ("headers.csv", b"a,b,c\n", "text/csv")}
    )
    assert response.status_code == 400


def test_get_nonexistent_dataset_returns_404(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/datasets/{fake_id}").status_code == 404


def test_delete_nonexistent_dataset_returns_404(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert client.delete(f"/datasets/{fake_id}").status_code == 404


# ---------------------------------------------------------------------------
# Safety: malicious headers cannot reach raw SQL
# ---------------------------------------------------------------------------


def test_malicious_header_is_sanitized_not_executed(client, db_session):
    # Properly CSV-quoted so the file itself is valid (a real attacker's
    # best shot: the header text is entirely attacker-controlled, but it
    # still has to survive being one well-formed CSV field).
    malicious_csv = b'id,"\'); DROP TABLE datasets; --"\n1,10\n2,20\n'
    response = client.post(
        "/datasets/upload", files={"file": ("attack.csv", malicious_csv, "text/csv")}
    )
    assert response.status_code == 201

    # The `datasets` table must still exist and be queryable - a real
    # injection would have dropped it.
    count = db_session.execute(text("SELECT COUNT(*) FROM datasets")).scalar()
    assert count >= 1

    columns = client.get(f"/datasets/{response.json()['id']}/columns").json()
    column_names = {c["column_name"] for c in columns}
    assert all(name.replace("_", "").isalnum() or name == "" for name in column_names)
    assert ";" not in "".join(column_names)
