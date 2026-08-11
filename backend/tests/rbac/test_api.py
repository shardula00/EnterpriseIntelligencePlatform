"""Integration tests: permission enforcement on real HTTP endpoints,
against a live Postgres. Covers both the existing Phase 2/3 routes (now
protected) and the new admin user-management API.
"""

import uuid

from tests.conftest import FIXTURES_DIR


def _unique_email() -> str:
    return f"rbac-api-{uuid.uuid4().hex[:8]}@example.com"


def _upload_orders_sample(auth_client):
    path = FIXTURES_DIR / "orders_sample.csv"
    files = {"file": ("orders_sample.csv", path.read_bytes(), "text/csv")}
    response = auth_client.post("/datasets/upload", files=files)
    assert response.status_code == 201
    return response.json()["id"]


# ---------------------------------------------------------------------------
# 401 unauthenticated
# ---------------------------------------------------------------------------


def test_unauthenticated_requests_are_rejected(unauthenticated_client):
    assert unauthenticated_client.get("/datasets").status_code == 401
    assert unauthenticated_client.post("/datasets/upload").status_code == 401
    assert unauthenticated_client.get("/users").status_code == 401
    assert unauthenticated_client.get("/audit-logs").status_code == 401


def test_health_and_auth_register_login_remain_public(unauthenticated_client):
    assert unauthenticated_client.get("/health").status_code == 200
    # 422 (bad body), not 401 - proves these routes don't require auth at all.
    assert unauthenticated_client.post("/auth/register", json={}).status_code == 422
    assert unauthenticated_client.post("/auth/login", json={}).status_code == 422


# ---------------------------------------------------------------------------
# VIEWER restrictions
# ---------------------------------------------------------------------------


def test_viewer_can_read_datasets_and_dashboard_summary(client, viewer_headers):
    dataset_id = _upload_orders_sample(client)

    assert client.get("/datasets", headers=viewer_headers).status_code == 200
    assert client.get(f"/datasets/{dataset_id}", headers=viewer_headers).status_code == 200
    assert client.get(f"/datasets/{dataset_id}/kpis", headers=viewer_headers).status_code == 200


def test_viewer_cannot_create_datasets(client, viewer_headers):
    path = FIXTURES_DIR / "orders_sample.csv"
    files = {"file": ("orders_sample.csv", path.read_bytes(), "text/csv")}
    response = client.post("/datasets/upload", files=files, headers=viewer_headers)
    assert response.status_code == 403


def test_viewer_cannot_delete_datasets(client, viewer_headers):
    dataset_id = _upload_orders_sample(client)
    response = client.delete(f"/datasets/{dataset_id}", headers=viewer_headers)
    assert response.status_code == 403


def test_viewer_cannot_configure_dashboard_breakdown(client, viewer_headers):
    dataset_id = _upload_orders_sample(client)
    response = client.get(
        f"/datasets/{dataset_id}/kpis/breakdown",
        params={"group_by": "region"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_viewer_cannot_access_user_management(client, viewer_headers):
    assert client.get("/users", headers=viewer_headers).status_code == 403


def test_viewer_cannot_access_audit_logs(client, viewer_headers):
    assert client.get("/audit-logs", headers=viewer_headers).status_code == 403


# ---------------------------------------------------------------------------
# ANALYST permissions
# ---------------------------------------------------------------------------


def test_analyst_can_create_datasets(client, analyst_headers):
    path = FIXTURES_DIR / "orders_sample.csv"
    files = {"file": ("orders_sample.csv", path.read_bytes(), "text/csv")}
    response = client.post("/datasets/upload", files=files, headers=analyst_headers)
    assert response.status_code == 201


def test_analyst_can_configure_dashboard_breakdown_and_trend(client, analyst_headers):
    dataset_id = _upload_orders_sample(client)

    breakdown = client.get(
        f"/datasets/{dataset_id}/kpis/breakdown",
        params={"group_by": "region", "metric": "quantity", "agg": "sum"},
        headers=analyst_headers,
    )
    assert breakdown.status_code == 200

    trend = client.get(
        f"/datasets/{dataset_id}/kpis/trend",
        params={"date_column": "order_date", "metric": "quantity"},
        headers=analyst_headers,
    )
    assert trend.status_code == 200


def test_analyst_cannot_delete_datasets(client, analyst_headers):
    dataset_id = _upload_orders_sample(client)
    response = client.delete(f"/datasets/{dataset_id}", headers=analyst_headers)
    assert response.status_code == 403


def test_analyst_cannot_access_user_management(client, analyst_headers):
    assert client.get("/users", headers=analyst_headers).status_code == 403


# ---------------------------------------------------------------------------
# ADMIN permissions
# ---------------------------------------------------------------------------


def test_admin_can_delete_datasets(client):
    dataset_id = _upload_orders_sample(client)
    assert client.delete(f"/datasets/{dataset_id}").status_code == 204


def test_admin_can_access_user_management_and_audit_logs(client):
    assert client.get("/users").status_code == 200
    assert client.get("/audit-logs").status_code == 200


# ---------------------------------------------------------------------------
# Multiple roles -> union of permissions
# ---------------------------------------------------------------------------


def test_user_with_viewer_and_analyst_roles_gets_the_union(client, viewer_user):
    # Add ANALYST on top of the existing VIEWER role via the real API.
    response = client.post(
        f"/users/{viewer_user.id}/roles", json={"role_names": ["VIEWER", "ANALYST"]}
    )
    assert response.status_code == 200
    assert set(response.json()["roles"]) == {"VIEWER", "ANALYST"}


# ---------------------------------------------------------------------------
# Admin user management API
# ---------------------------------------------------------------------------


def test_admin_can_list_and_get_users(client, viewer_user):
    listing = client.get("/users")
    assert listing.status_code == 200
    assert any(u["id"] == str(viewer_user.id) for u in listing.json())

    detail = client.get(f"/users/{viewer_user.id}")
    assert detail.status_code == 200
    assert detail.json()["email"] == viewer_user.email


def test_admin_can_create_a_user(client):
    email = _unique_email()
    response = client.post(
        "/users", json={"email": email, "password": "Password123", "full_name": "Created By Admin"}
    )
    assert response.status_code == 201
    assert response.json()["roles"] == ["VIEWER"]


def test_admin_can_deactivate_and_reactivate_a_user(client, viewer_user):
    deactivate = client.patch(f"/users/{viewer_user.id}", json={"is_active": False})
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    reactivate = client.patch(f"/users/{viewer_user.id}", json={"is_active": True})
    assert reactivate.status_code == 200
    assert reactivate.json()["is_active"] is True


def test_admin_can_change_a_users_role(client, viewer_user):
    response = client.post(f"/users/{viewer_user.id}/roles", json={"role_names": ["ANALYST"]})
    assert response.status_code == 200
    assert response.json()["roles"] == ["ANALYST"]


def test_assigning_an_unknown_role_returns_400(client, viewer_user):
    response = client.post(f"/users/{viewer_user.id}/roles", json={"role_names": ["SUPERUSER"]})
    assert response.status_code == 400


def test_admin_can_delete_a_user(client, viewer_user):
    response = client.delete(f"/users/{viewer_user.id}")
    assert response.status_code == 204
    assert client.get(f"/users/{viewer_user.id}").status_code == 404


def test_updating_unknown_user_returns_404(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/users/{fake_id}").status_code == 404
    assert client.patch(f"/users/{fake_id}", json={"is_active": False}).status_code == 404


# ---------------------------------------------------------------------------
# Self-privilege-escalation prevention
# ---------------------------------------------------------------------------


def test_admin_cannot_change_their_own_role(client, admin_user):
    response = client.post(f"/users/{admin_user.id}/roles", json={"role_names": ["VIEWER"]})
    assert response.status_code == 403


def test_admin_cannot_deactivate_themselves(client, admin_user):
    response = client.patch(f"/users/{admin_user.id}", json={"is_active": False})
    assert response.status_code == 403


def test_admin_cannot_delete_their_own_account(client, admin_user):
    response = client.delete(f"/users/{admin_user.id}")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Role/permission catalog endpoints (needed by the admin UI)
# ---------------------------------------------------------------------------


def test_roles_catalog_lists_the_three_fixed_roles(client):
    response = client.get("/roles")
    assert response.status_code == 200
    assert {r["name"] for r in response.json()} == {"ADMIN", "ANALYST", "VIEWER"}


def test_permissions_catalog_lists_all_thirteen_permissions(client):
    # 10 from Phase 4 (dataset/dashboard/user/audit) + 3 added in Phase 5
    # (ml:read, ml:train, ml:predict) - see app/rbac/seed.py.
    response = client.get("/permissions")
    assert response.status_code == 200
    assert len(response.json()) == 13
