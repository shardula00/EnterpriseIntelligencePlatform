"""Decision Intelligence API (Phase 11): propose/list/inspect
recommendations, approve/reject them, and run a standalone what-if
scenario.

Thin HTTP layer only - all logic lives in app/decision/service.py.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record_event
from app.config import Settings, get_settings
from app.db import get_db
from app.decision import service
from app.decision.errors import InvalidDecisionActionError, RecommendationNotFoundError
from app.decision.schemas import (
    RecommendationOut,
    RecommendationRequest,
    RecommendationSummaryOut,
    ScenarioRequest,
    ScenarioResultOut,
)
from app.ingestion.errors import DatasetNotFoundError
from app.models.decision import Recommendation
from app.models.user import User
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/decisions", tags=["decisions"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_out(record: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=record.id,
        dataset_id=record.dataset_id,
        question=record.question,
        recommendation=record.recommendation,
        alternatives=record.alternatives,
        evidence=record.evidence,
        risks=record.risks,
        assumptions=record.assumptions,
        confidence=record.confidence,
        expected_impact=record.expected_impact,
        status=record.status,
        decided_by=record.decided_by,
        decided_at=record.decided_at,
        created_at=record.created_at,
    )


@router.post("", response_model=RecommendationOut, status_code=201)
def propose(
    request: Request,
    body: RecommendationRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("decision:propose")),
) -> RecommendationOut:
    try:
        record = service.propose_recommendation(
            db, settings, current_user, body.dataset_id, body.question
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.DECISION_PROPOSED,
        resource_type="recommendation",
        resource_id=str(record.id),
        metadata={"dataset_id": str(record.dataset_id), "confidence": record.confidence},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return _to_out(record)


@router.post("/scenario", response_model=ScenarioResultOut)
def scenario(
    body: ScenarioRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("decision:propose")),
) -> ScenarioResultOut:
    try:
        result = service.run_scenario_only(db, settings, body.dataset_id, body.question)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ScenarioResultOut(
        computed=result.computed,
        question=result.question,
        affected_metric=result.affected_metric,
        perturbed_metric=result.perturbed_metric,
        delta_percent=result.delta_percent,
        baseline_perturbed_value=result.baseline_perturbed_value,
        baseline_affected_value=result.baseline_affected_value,
        new_perturbed_value=result.new_perturbed_value,
        new_affected_value=result.new_affected_value,
        affected_value_change=result.affected_value_change,
        relationship=result.relationship,
        note=result.note,
        reason=result.reason,
    )


@router.get("", response_model=list[RecommendationSummaryOut])
def list_recommendations(
    dataset_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("decision:read")),
) -> list[RecommendationSummaryOut]:
    records = service.list_recommendations(db, dataset_id=dataset_id)
    return [
        RecommendationSummaryOut(
            id=r.id,
            dataset_id=r.dataset_id,
            question=r.question,
            recommendation=r.recommendation,
            confidence=r.confidence,
            status=r.status,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/{recommendation_id}", response_model=RecommendationOut)
def get_recommendation(
    recommendation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("decision:read")),
) -> RecommendationOut:
    try:
        record = service.get_recommendation(db, recommendation_id)
    except RecommendationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_out(record)


def _decide(
    request: Request,
    recommendation_id: UUID,
    db: Session,
    current_user: User,
    action: str,
    audit_action: str,
) -> RecommendationOut:
    try:
        if action == "approve":
            record = service.approve_recommendation(db, recommendation_id, current_user)
        else:
            record = service.reject_recommendation(db, recommendation_id, current_user)
    except RecommendationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDecisionActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    record_event(
        db,
        user_id=current_user.id,
        action=audit_action,
        resource_type="recommendation",
        resource_id=str(record.id),
        metadata={"status": record.status},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return _to_out(record)


@router.post("/{recommendation_id}/approve", response_model=RecommendationOut)
def approve(
    recommendation_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    # ADMIN-only - see app/rbac/seed.py, the same mlops:promote precedent
    # (proposing/evaluating is ANALYST-reachable, signing off is not).
    current_user: User = Depends(require_permission("decision:approve")),
) -> RecommendationOut:
    return _decide(request, recommendation_id, db, current_user, "approve", AuditAction.DECISION_APPROVED)


@router.post("/{recommendation_id}/reject", response_model=RecommendationOut)
def reject(
    recommendation_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("decision:approve")),
) -> RecommendationOut:
    return _decide(request, recommendation_id, db, current_user, "reject", AuditAction.DECISION_REJECTED)
