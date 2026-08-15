"""Integration tests for the document API (Phase 7), against a live
Postgres, hitting the real HTTP endpoints - permission enforcement,
ownership enforcement, and audit events."""

from tests.conftest import FIXTURES_DIR

RAG_FIXTURES = FIXTURES_DIR / "rag"


def _upload(client, filename: str, content_type: str = "text/plain"):
    path = RAG_FIXTURES / filename
    files = {"file": (filename, path.read_bytes(), content_type)}
    response = client.post("/documents/upload", files=files)
    assert response.status_code == 201, response.text
    return response.json()


def _upload_and_process(client, filename: str = "employee_handbook_policies.txt"):
    document = _upload(client, filename)
    response = client.post(f"/documents/{document['id']}/process")
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Upload / list / detail / process
# ---------------------------------------------------------------------------


def test_upload_document_returns_uploaded_status(client):
    document = _upload(client, "employee_handbook_policies.txt")
    assert document["status"] == "uploaded"
    assert document["document_type"] == "txt"
    assert document["chunk_count"] == 0


def test_upload_rejects_an_unsupported_file_type(client):
    files = {"file": ("malware.exe", b"not a real document", "application/octet-stream")}
    response = client.post("/documents/upload", files=files)
    assert response.status_code == 400


def test_upload_rejects_an_empty_file(client):
    files = {"file": ("empty.txt", b"", "text/plain")}
    response = client.post("/documents/upload", files=files)
    assert response.status_code == 400


def test_process_document_reaches_ready_with_chunks(client):
    document = _upload_and_process(client)
    assert document["status"] == "ready"
    assert document["chunk_count"] > 0


def test_process_a_malformed_pdf_reaches_failed_not_a_500(client):
    files = {"file": ("broken.pdf", b"%PDF-1.4 not a real pdf body", "application/pdf")}
    upload_response = client.post("/documents/upload", files=files)
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    process_response = client.post(f"/documents/{document_id}/process")
    assert process_response.status_code == 200
    body = process_response.json()
    assert body["status"] == "failed"
    assert body["error_message"]


def test_get_document_detail_includes_chunks(client):
    document = _upload_and_process(client)
    response = client.get(f"/documents/{document['id']}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["chunks"]) == body["chunk_count"]


def test_list_documents_includes_the_uploaded_document(client):
    document = _upload(client, "pricing_guide.md", content_type="text/markdown")
    response = client.get("/documents")
    assert response.status_code == 200
    assert any(d["id"] == document["id"] for d in response.json())


def test_delete_document_removes_it(client):
    document = _upload(client, "employee_handbook_policies.txt")
    response = client.delete(f"/documents/{document['id']}")
    assert response.status_code == 204
    assert client.get(f"/documents/{document['id']}").status_code == 404


def test_get_unknown_document_returns_404(client):
    import uuid

    response = client.get(f"/documents/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# RBAC - permission tier enforcement
# ---------------------------------------------------------------------------


def test_unauthenticated_request_is_rejected(unauthenticated_client):
    response = unauthenticated_client.get("/documents")
    assert response.status_code == 401


def test_viewer_can_read_but_not_upload(client, viewer_headers):
    upload_response = client.post(
        "/documents/upload",
        files={"file": ("a.txt", b"some content here", "text/plain")},
        headers=viewer_headers,
    )
    assert upload_response.status_code == 403

    list_response = client.get("/documents", headers=viewer_headers)
    assert list_response.status_code == 200


def test_analyst_can_upload_and_delete(client, analyst_headers):
    upload_response = client.post(
        "/documents/upload",
        files={"file": ("a.txt", b"some content here", "text/plain")},
        headers=analyst_headers,
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    delete_response = client.delete(f"/documents/{document_id}", headers=analyst_headers)
    assert delete_response.status_code == 204


# ---------------------------------------------------------------------------
# Ownership - Phase 7 §11 (a permission check is not the same as an
# ownership check - both are exercised here)
# ---------------------------------------------------------------------------


def test_a_second_user_cannot_view_another_users_document(client, analyst_headers):
    """`client` is admin-authenticated; upload as admin, then confirm a
    completely different (non-admin) authenticated user is denied."""
    document = _upload(client, "employee_handbook_policies.txt")

    response = client.get(f"/documents/{document['id']}", headers=analyst_headers)
    assert response.status_code == 404


def test_a_second_user_cannot_list_another_users_document(client, analyst_headers):
    document = _upload(client, "employee_handbook_policies.txt")

    listed = client.get("/documents", headers=analyst_headers).json()
    assert all(d["id"] != document["id"] for d in listed)


def test_a_second_user_cannot_delete_another_users_document(client, analyst_headers):
    document = _upload(client, "employee_handbook_policies.txt")

    response = client.delete(f"/documents/{document['id']}", headers=analyst_headers)
    assert response.status_code == 404
    # Still there, from the actual owner's point of view.
    assert client.get(f"/documents/{document['id']}").status_code == 200


def test_admin_can_view_any_users_document(client, analyst_headers, analyst_user):
    upload_response = client.post(
        "/documents/upload",
        files={"file": ("a.txt", b"analyst's own content", "text/plain")},
        headers=analyst_headers,
    )
    document_id = upload_response.json()["id"]

    response = client.get(f"/documents/{document_id}")  # client == admin
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


def test_upload_and_process_are_audited(client):
    document = _upload_and_process(client)

    audit = client.get(
        "/audit-logs", params={"resource_type": "document", "resource_id": document["id"]}
    ).json()
    actions = {entry["action"] for entry in audit["items"]}
    assert "rag.document_uploaded" in actions
    assert "rag.document_processed" in actions


def test_deletion_is_audited(client):
    document = _upload(client, "employee_handbook_policies.txt")
    client.delete(f"/documents/{document['id']}")

    audit = client.get(
        "/audit-logs", params={"resource_type": "document", "resource_id": document["id"]}
    ).json()
    actions = {entry["action"] for entry in audit["items"]}
    assert "rag.document_deleted" in actions
