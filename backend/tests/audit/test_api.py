"""Integration tests: audit events actually produced by real actions, via
the real HTTP API, plus the GET /audit-logs endpoint itself.

Permission enforcement on /audit-logs (401/403) is covered in
tests/rbac/test_api.py - this file focuses on audit *content*: does the
right event show up, with the right resource_id, and never a secret.
"""

from tests.conftest import FIXTURES_DIR


def _upload_orders_sample(client):
    path = FIXTURES_DIR / "orders_sample.csv"
    files = {"file": ("orders_sample.csv", path.read_bytes(), "text/csv")}
    response = client.post("/datasets/upload", files=files)
    assert response.status_code == 201
    return response.json()["id"]


def test_dataset_upload_creates_an_audit_event(client):
    dataset_id = _upload_orders_sample(client)

    logs = client.get("/audit-logs", params={"action": "dataset.uploaded"}).json()
    matching = [e for e in logs["items"] if e["resource_id"] == dataset_id]
    assert len(matching) == 1
    assert matching[0]["resource_type"] == "dataset"
    assert matching[0]["event_metadata"]["row_count"] == 20


def test_dataset_deletion_creates_an_audit_event(client):
    dataset_id = _upload_orders_sample(client)
    client.delete(f"/datasets/{dataset_id}")

    logs = client.get("/audit-logs", params={"action": "dataset.deleted"}).json()
    matching = [e for e in logs["items"] if e["resource_id"] == dataset_id]
    assert len(matching) == 1
    # The audit record must outlive the dataset it describes.
    assert client.get(f"/datasets/{dataset_id}").status_code == 404


def test_role_change_creates_an_audit_event(client, viewer_user):
    client.post(f"/users/{viewer_user.id}/roles", json={"role_names": ["ANALYST"]})

    logs = client.get("/audit-logs", params={"action": "user.role_changed"}).json()
    matching = [e for e in logs["items"] if e["resource_id"] == str(viewer_user.id)]
    assert len(matching) == 1
    assert matching[0]["event_metadata"]["new_roles"] == ["ANALYST"]


def test_user_deactivation_creates_an_audit_event(client, viewer_user):
    client.patch(f"/users/{viewer_user.id}", json={"is_active": False})

    logs = client.get("/audit-logs", params={"action": "user.deactivated"}).json()
    matching = [e for e in logs["items"] if e["resource_id"] == str(viewer_user.id)]
    assert len(matching) == 1


def test_no_audit_event_anywhere_contains_a_password_or_token(
    client, viewer_user, unauthenticated_client
):
    # Exercise a realistic mix of actions, then sweep every recorded event.
    _upload_orders_sample(client)
    client.post(f"/users/{viewer_user.id}/roles", json={"role_names": ["ANALYST"]})
    unauthenticated_client.post(
        "/auth/register",
        json={
            "email": "sweep-test@example.com",
            "password": "SweepPassword123",
            "full_name": "Sweep",
        },
    )
    unauthenticated_client.post(
        "/auth/login", json={"email": "sweep-test@example.com", "password": "SweepPassword123"}
    )

    logs = client.get("/audit-logs", params={"limit": 100}).json()
    for entry in logs["items"]:
        dumped = str(entry)
        assert "SweepPassword123" not in dumped
        assert "$argon2" not in dumped  # no password hash either
        assert "Bearer " not in dumped


def test_audit_logs_endpoint_supports_pagination(client, viewer_user):
    for role_names in (["ANALYST"], ["VIEWER"], ["ANALYST"]):
        client.post(f"/users/{viewer_user.id}/roles", json={"role_names": role_names})

    params = {"action": "user.role_changed", "limit": 2, "offset": 0}
    page = client.get("/audit-logs", params=params).json()
    assert page["limit"] == 2
    assert page["offset"] == 0
    assert len(page["items"]) == 2
    assert page["total"] >= 3
