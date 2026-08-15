"""Enterprise document API: upload, list, inspect, process, delete.

Thin HTTP layer only - all pipeline logic lives in app/rag/service.py.
Every document-scoped endpoint is both permission-gated (RBAC) and
ownership-scoped (a document is only visible to its uploader or an ADMIN -
see app/rag/service.py's _ensure_access) - two independent checks, neither
a substitute for the other.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record_event
from app.config import Settings, get_settings
from app.db import get_db
from app.models.document import Document
from app.models.user import User
from app.rag import service
from app.rag.embeddings import get_embedding_provider
from app.rag.errors import (
    DocumentNotFoundError,
    DocumentTooLargeError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)
from app.rag.schemas import DocumentDetailOut, DocumentOut
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/documents", tags=["documents"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _get_document_or_404(db: Session, document_id: UUID, user: User) -> Document:
    try:
        return service.get_document(db, document_id, user)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/upload", response_model=DocumentOut, status_code=201)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("rag:upload")),
) -> DocumentOut:
    content = file.file.read()
    try:
        document = service.upload_document(
            db, settings, file.filename or "upload", content, current_user.id
        )
    except (UnsupportedDocumentTypeError, EmptyDocumentError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.DOCUMENT_UPLOADED,
        resource_type="document",
        resource_id=str(document.id),
        metadata={
            "filename": document.filename,
            "document_type": document.document_type,
            "file_size_bytes": document.file_size_bytes,
        },
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return DocumentOut.model_validate(document, from_attributes=True)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("rag:read")),
) -> list[DocumentOut]:
    documents = service.list_documents(db, current_user, status=status)
    return [DocumentOut.model_validate(d, from_attributes=True) for d in documents]


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("rag:read")),
) -> DocumentDetailOut:
    document = _get_document_or_404(db, document_id, current_user)
    return DocumentDetailOut.model_validate(document, from_attributes=True)


@router.post("/{document_id}/process", response_model=DocumentOut)
def process_document(
    request: Request,
    document_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("rag:upload")),
) -> DocumentOut:
    _get_document_or_404(db, document_id, current_user)  # 404 before doing any work
    embedding_provider = get_embedding_provider(settings)
    document = service.process_document(db, settings, embedding_provider, document_id, current_user)

    if document.status == "ready":
        action, metadata = AuditAction.DOCUMENT_PROCESSED, {"chunk_count": document.chunk_count}
    else:
        action, metadata = AuditAction.DOCUMENT_PROCESSING_FAILED, {"error": document.error_message}
    record_event(
        db,
        user_id=current_user.id,
        action=action,
        resource_type="document",
        resource_id=str(document.id),
        metadata=metadata,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return DocumentOut.model_validate(document, from_attributes=True)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("rag:upload")),
) -> None:
    document = _get_document_or_404(db, document_id, current_user)

    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.DOCUMENT_DELETED,
        resource_type="document",
        resource_id=str(document.id),
        metadata={"filename": document.filename},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    service.delete_document(db, settings, document_id, current_user)
