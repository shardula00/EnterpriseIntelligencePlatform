"""MLOps API (Phase 6): model registry, drift detection, performance
monitoring, alerts.

Thin HTTP layer only - all computation lives in app/mlops/service.py.
Three permissions gate this router (see app/rbac/seed.py): `mlops:read`
(registry/version/drift/monitoring/alert viewing), `mlops:evaluate`
(register a version, run a drift/performance check), `mlops:promote`
(promote/archive - ADMIN-only by default, same governance tier as
dataset:delete).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record_event
from app.config import Settings, get_settings
from app.db import get_db
from app.ingestion.errors import DatasetNotFoundError
from app.ml.errors import ArtifactNotFoundError, MlRunNotFoundError
from app.mlops import service
from app.mlops.errors import (
    AlreadyRegisteredError,
    InsufficientDataForMonitoringError,
    InvalidLifecycleTransitionError,
    ModelVersionNotFoundError,
)
from app.mlops.schemas import (
    DriftCheckRequest,
    DriftResultOut,
    ModelVersionDetailOut,
    ModelVersionOut,
    MonitoringEventOut,
    PerformanceCheckOut,
    PerformanceCheckRequest,
    PromoteModelVersionRequest,
    RegisterModelVersionRequest,
)
from app.models.model_version import ModelVersion
from app.models.monitoring_event import MonitoringEvent
from app.models.user import User
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/mlops", tags=["mlops"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_version_out(version: ModelVersion) -> ModelVersionOut:
    return ModelVersionOut.model_validate(version, from_attributes=True)


def _to_event_out(event: MonitoringEvent) -> MonitoringEventOut:
    return MonitoringEventOut.model_validate(event, from_attributes=True)


def _record(
    request: Request, db: Session, user: User, action: str, resource_id: str, metadata: dict
) -> None:
    record_event(
        db, user_id=user.id, action=action, resource_type="model_version", resource_id=resource_id,
        metadata=metadata, ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@router.post("/model-versions", response_model=ModelVersionOut, status_code=201)
def register_model_version(
    request: Request,
    body: RegisterModelVersionRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("mlops:evaluate")),
) -> ModelVersionOut:
    try:
        version = service.register_model_version(db, settings, body.ml_run_id, current_user.id)
    except MlRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _record(
        request, db, current_user, AuditAction.MODEL_VERSION_REGISTERED, str(version.id),
        {
            "ml_run_id": str(version.ml_run_id),
            "task_type": version.task_type,
            "version_number": version.version_number,
        },
    )
    return _to_version_out(version)


@router.get("/model-versions", response_model=list[ModelVersionOut])
def list_model_versions(
    dataset_id: UUID | None = None,
    task_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("mlops:read")),
) -> list[ModelVersionOut]:
    versions = service.list_model_versions(
        db, dataset_id=dataset_id, task_type=task_type, status=status
    )
    return [_to_version_out(v) for v in versions]


@router.get("/model-versions/{version_id}", response_model=ModelVersionDetailOut)
def get_model_version(
    version_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("mlops:read")),
) -> ModelVersionDetailOut:
    try:
        version, run_results = service.get_model_version_detail(db, version_id)
    except (ModelVersionNotFoundError, MlRunNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ModelVersionDetailOut(version=_to_version_out(version), run=run_results)


@router.post("/model-versions/{version_id}/promote", response_model=ModelVersionOut)
def promote_model_version(
    request: Request,
    version_id: UUID,
    body: PromoteModelVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("mlops:promote")),
) -> ModelVersionOut:
    try:
        version, auto_archived = service.promote_model_version(
            db, version_id, body.target_status, current_user.id
        )
    except (ModelVersionNotFoundError, MlRunNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record(
        request, db, current_user, AuditAction.MODEL_VERSION_PROMOTED, str(version.id),
        {
            "new_status": version.status,
            "auto_archived_version_id": str(auto_archived.id) if auto_archived else None,
        },
    )
    return _to_version_out(version)


@router.post("/model-versions/{version_id}/archive", response_model=ModelVersionOut)
def archive_model_version(
    request: Request,
    version_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("mlops:promote")),
) -> ModelVersionOut:
    try:
        version = service.archive_model_version(db, version_id, current_user.id)
    except ModelVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record(request, db, current_user, AuditAction.MODEL_VERSION_ARCHIVED, str(version.id), {})
    return _to_version_out(version)


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------


@router.post("/model-versions/{version_id}/drift-check", response_model=DriftResultOut)
def run_drift_check(
    request: Request,
    version_id: UUID,
    body: DriftCheckRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("mlops:evaluate")),
) -> DriftResultOut:
    try:
        payload, event = service.run_drift_check(
            db, settings, version_id, body.dataset_id, current_user.id
        )
    except (ModelVersionNotFoundError, MlRunNotFoundError, DatasetNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _record(
        request, db, current_user, AuditAction.DRIFT_CHECK_RUN, str(version_id),
        {
            "dataset_id": str(body.dataset_id),
            "overall_status": payload["overall_status"],
            "event_id": str(event.id),
        },
    )
    return DriftResultOut(**payload)


# ---------------------------------------------------------------------------
# Performance monitoring
# ---------------------------------------------------------------------------


@router.post("/model-versions/{version_id}/performance-check", response_model=PerformanceCheckOut)
def run_performance_check(
    request: Request,
    version_id: UUID,
    body: PerformanceCheckRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("mlops:evaluate")),
) -> PerformanceCheckOut:
    try:
        payload, event = service.run_performance_check(
            db, settings, version_id, body.dataset_id, current_user.id
        )
    except (ModelVersionNotFoundError, MlRunNotFoundError, DatasetNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except InsufficientDataForMonitoringError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record(
        request, db, current_user, AuditAction.PERFORMANCE_CHECK_RUN, str(version_id),
        {
            "dataset_id": str(body.dataset_id),
            "status": payload["status"],
            "event_id": str(event.id),
        },
    )
    return PerformanceCheckOut(**payload)


# ---------------------------------------------------------------------------
# Monitoring events / alerts
# ---------------------------------------------------------------------------


@router.get("/monitoring-events", response_model=list[MonitoringEventOut])
def list_monitoring_events(
    model_version_id: UUID | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("mlops:read")),
) -> list[MonitoringEventOut]:
    events = service.list_monitoring_events(
        db, model_version_id=model_version_id, event_type=event_type, severity=severity
    )
    return [_to_event_out(e) for e in events]
