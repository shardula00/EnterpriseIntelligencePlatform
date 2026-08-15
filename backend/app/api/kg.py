"""Knowledge graph API: build/rebuild a dataset's entity/relationship
graph (Phase 9).

Thin HTTP layer only - all logic lives in app/kg/service.py. Deliberately
no standalone graph-browsing endpoints: graph evidence only ever surfaces
through POST /rag/query in hybrid mode (see app/rag/service.py) - see
app/kg/__init__.py for why.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record_event
from app.db import get_db
from app.ingestion.errors import DatasetNotFoundError
from app.kg import service
from app.kg.schemas import GraphBuildResultOut
from app.models.user import User
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/datasets", tags=["knowledge-graph"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/{dataset_id}/graph/build", response_model=GraphBuildResultOut)
def build_graph(
    dataset_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    # Reuses dataset:create (not a new kg:* permission) - building a
    # dataset's graph is analogous to any other dataset-derived processing
    # step, per the approved Phase 9 design.
    current_user: User = Depends(require_permission("dataset:create")),
) -> GraphBuildResultOut:
    try:
        result = service.build_graph_for_dataset(db, dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.KG_BUILT,
        resource_type="dataset",
        resource_id=str(dataset_id),
        metadata={
            "entity_count": result.entity_count,
            "relationship_count": result.relationship_count,
            "entity_types": result.entity_types,
        },
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    return GraphBuildResultOut(
        dataset_id=dataset_id,
        entity_count=result.entity_count,
        relationship_count=result.relationship_count,
        entity_types=result.entity_types,
    )
