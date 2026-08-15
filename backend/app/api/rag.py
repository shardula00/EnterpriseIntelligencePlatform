"""RAG query API: ask a question, inspect past queries.

Thin HTTP layer only - all pipeline logic lives in app/rag/service.py.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record_event
from app.config import Settings, get_settings
from app.db import get_db
from app.models.user import User
from app.rag import service
from app.rag.embeddings import get_embedding_provider
from app.rag.errors import RagQueryNotFoundError
from app.rag.llm import get_llm_provider
from app.rag.schemas import RagQueryOut, RagQueryRequest, RagQuerySummaryOut
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/rag", tags=["rag"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/query", response_model=RagQueryOut)
def run_query(
    request: Request,
    body: RagQueryRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("rag:query")),
) -> RagQueryOut:
    embedding_provider = get_embedding_provider(settings)
    llm_provider = get_llm_provider(settings)

    query = service.run_query(
        db,
        settings,
        embedding_provider,
        llm_provider,
        current_user,
        body.question,
        document_ids=body.document_ids,
        top_k=body.top_k,
    )

    # Deliberately no question/answer/source-excerpt text in the audit
    # metadata - those can contain private document content, and the
    # question itself is enough to correlate this event without it.
    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.RAG_QUERY_PERFORMED,
        resource_type="rag_query",
        resource_id=str(query.id),
        metadata={"status": query.status, "source_count": len(query.sources)},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return RagQueryOut.model_validate(query, from_attributes=True)


@router.get("/queries", response_model=list[RagQuerySummaryOut])
def list_queries(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("rag:read")),
) -> list[RagQuerySummaryOut]:
    queries = service.list_queries(db, current_user)
    return [
        RagQuerySummaryOut(
            id=q.id, question=q.question, status=q.status,
            source_count=len(q.sources), created_at=q.created_at,
        )
        for q in queries
    ]


@router.get("/queries/{query_id}", response_model=RagQueryOut)
def get_query(
    query_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("rag:read")),
) -> RagQueryOut:
    try:
        query = service.get_query(db, query_id, current_user)
    except RagQueryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RagQueryOut.model_validate(query, from_attributes=True)
