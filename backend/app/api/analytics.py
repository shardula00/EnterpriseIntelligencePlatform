"""Natural-language analytics API: ask a question against a dataset,
inspect past queries.

Thin HTTP layer only - all pipeline logic lives in app/analytics/service.py.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.analytics import service
from app.analytics.schemas import AnalyticsQueryOut, AnalyticsQueryRequest, AnalyticsQuerySummaryOut
from app.audit.service import AuditAction, record_event
from app.config import Settings, get_settings
from app.db import get_db
from app.ingestion.errors import DatasetNotFoundError
from app.models.analytics import AnalyticsQuery
from app.models.user import User
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_out(query: AnalyticsQuery) -> AnalyticsQueryOut:
    return AnalyticsQueryOut(
        id=query.id,
        dataset_id=query.dataset_id,
        dataset_name=query.dataset.name,
        question=query.question,
        status=query.status,
        generated_sql=query.generated_sql,
        intent=query.intent,
        error_message=query.error_message,
        columns=query.columns,
        rows=query.rows,
        row_count=query.row_count,
        created_at=query.created_at,
    )


@router.post("/query", response_model=AnalyticsQueryOut)
def run_query(
    request: Request,
    body: AnalyticsQueryRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("analytics:query")),
) -> AnalyticsQueryOut:
    try:
        query = service.run_query(db, settings, body.dataset_id, body.question, current_user.id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Deliberately no generated_sql/rows in the audit metadata - those can
    # reflect private dataset content; the question and outcome are enough
    # to correlate this event without it (same reasoning as
    # app/api/rag.py's RAG_QUERY_PERFORMED event).
    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.ANALYTICS_QUERY_PERFORMED,
        resource_type="dataset",
        resource_id=str(query.dataset_id),
        metadata={"status": query.status, "row_count": query.row_count},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return _to_out(query)


@router.get("/queries", response_model=list[AnalyticsQuerySummaryOut])
def list_queries(
    dataset_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
) -> list[AnalyticsQuerySummaryOut]:
    queries = service.list_queries(db, dataset_id=dataset_id)
    return [
        AnalyticsQuerySummaryOut(
            id=q.id,
            dataset_id=q.dataset_id,
            dataset_name=q.dataset.name,
            question=q.question,
            status=q.status,
            row_count=q.row_count,
            created_at=q.created_at,
        )
        for q in queries
    ]


@router.get("/queries/{query_id}", response_model=AnalyticsQueryOut)
def get_query(
    query_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
) -> AnalyticsQueryOut:
    query = service.get_query(db, query_id)
    if query is None:
        raise HTTPException(status_code=404, detail=f"Analytics query {query_id} not found.")
    return _to_out(query)
