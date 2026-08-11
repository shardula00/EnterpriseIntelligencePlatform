"""Dataset ingestion API: upload, list, inspect schema/quality/lineage, preview, delete.

Thin HTTP layer only - all pipeline logic lives in app/ingestion/service.py.
This module's only job is request parsing, permission enforcement (Phase 4),
audit recording (Phase 4), and mapping ingestion errors onto HTTP status
codes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record_event
from app.config import Settings, get_settings
from app.db import get_db
from app.ingestion import service
from app.ingestion.errors import (
    DatasetNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    ParseError,
    UnsupportedFileTypeError,
)
from app.ingestion.schemas import (
    ColumnInfo,
    DatasetDetail,
    DatasetSummary,
    LineageEventOut,
    LineageOut,
    PreviewOut,
    QualityIssueOut,
    QualityReportOut,
)
from app.models.dataset import Dataset
from app.models.user import User
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_detail(dataset: Dataset) -> DatasetDetail:
    ordered_columns = sorted(dataset.columns, key=lambda c: c.position)
    return DatasetDetail(
        **DatasetSummary.model_validate(dataset).model_dump(),
        columns=[ColumnInfo.model_validate(c) for c in ordered_columns],
    )


def _get_dataset_or_404(db: Session, dataset_id: UUID) -> Dataset:
    try:
        return service.get_dataset(db, dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/upload", response_model=DatasetDetail, status_code=201)
def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    dataset_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("dataset:create")),
) -> DatasetDetail:
    content = file.file.read()
    try:
        dataset = service.ingest_upload(
            db, settings, file.filename or "upload", content, dataset_name
        )
    except (UnsupportedFileTypeError, EmptyFileError, ParseError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    # ingest_upload already committed the dataset itself (Phase 2's own
    # atomic transaction) - the audit entry is necessarily a second, small
    # transaction since the dataset's id doesn't exist until that returns.
    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.DATASET_UPLOADED,
        resource_type="dataset",
        resource_id=str(dataset.id),
        metadata={
            "name": dataset.name,
            "row_count": dataset.row_count,
            "file_type": dataset.file_type,
        },
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return _to_detail(dataset)


@router.get("", response_model=list[DatasetSummary])
def list_datasets(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("dataset:read")),
) -> list[DatasetSummary]:
    datasets = service.list_datasets(db, limit=limit, offset=offset)
    return [DatasetSummary.model_validate(d) for d in datasets]


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(
    dataset_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("dataset:read")),
) -> DatasetDetail:
    return _to_detail(_get_dataset_or_404(db, dataset_id))


@router.get("/{dataset_id}/columns", response_model=list[ColumnInfo])
def get_dataset_columns(
    dataset_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("dataset:read")),
) -> list[ColumnInfo]:
    dataset = _get_dataset_or_404(db, dataset_id)
    return [ColumnInfo.model_validate(c) for c in sorted(dataset.columns, key=lambda c: c.position)]


@router.get("/{dataset_id}/quality", response_model=QualityReportOut)
def get_dataset_quality(
    dataset_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("dataset:read")),
) -> QualityReportOut:
    dataset = _get_dataset_or_404(db, dataset_id)
    return QualityReportOut(
        dataset_id=dataset.id,
        quality_score=dataset.quality_score,
        issues=[QualityIssueOut.model_validate(i) for i in dataset.quality_issues],
    )


@router.get("/{dataset_id}/lineage", response_model=LineageOut)
def get_dataset_lineage(
    dataset_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("dataset:read")),
) -> LineageOut:
    dataset = _get_dataset_or_404(db, dataset_id)
    return LineageOut(
        dataset_id=dataset.id,
        events=[LineageEventOut.model_validate(e) for e in dataset.lineage_events],
    )


@router.get("/{dataset_id}/preview", response_model=PreviewOut)
def get_dataset_preview(
    dataset_id: UUID,
    limit: int = 20,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("dataset:read")),
) -> PreviewOut:
    _get_dataset_or_404(db, dataset_id)  # 404 before touching the physical table
    columns, rows = service.get_preview(db, dataset_id, limit=limit)
    return PreviewOut(dataset_id=dataset_id, columns=columns, rows=rows)


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(
    dataset_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("dataset:delete")),
) -> None:
    dataset = _get_dataset_or_404(db, dataset_id)

    # Added to the session before service.delete_dataset() so it commits
    # atomically together with the deletion, in that function's own
    # transaction - not a separate commit.
    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.DATASET_DELETED,
        resource_type="dataset",
        resource_id=str(dataset.id),
        metadata={"name": dataset.name},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    service.delete_dataset(db, dataset_id)
