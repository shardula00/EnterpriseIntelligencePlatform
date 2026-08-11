"""Dataset ingestion API: upload, list, inspect schema/quality/lineage, preview, delete.

Thin HTTP layer only - all pipeline logic lives in app/ingestion/service.py.
This module's only job is request parsing and mapping ingestion errors onto
HTTP status codes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

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

router = APIRouter(prefix="/datasets", tags=["datasets"])


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
    file: UploadFile = File(...),
    dataset_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
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
    return _to_detail(dataset)


@router.get("", response_model=list[DatasetSummary])
def list_datasets(
    limit: int = 50, offset: int = 0, db: Session = Depends(get_db)
) -> list[DatasetSummary]:
    datasets = service.list_datasets(db, limit=limit, offset=offset)
    return [DatasetSummary.model_validate(d) for d in datasets]


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: UUID, db: Session = Depends(get_db)) -> DatasetDetail:
    return _to_detail(_get_dataset_or_404(db, dataset_id))


@router.get("/{dataset_id}/columns", response_model=list[ColumnInfo])
def get_dataset_columns(dataset_id: UUID, db: Session = Depends(get_db)) -> list[ColumnInfo]:
    dataset = _get_dataset_or_404(db, dataset_id)
    return [ColumnInfo.model_validate(c) for c in sorted(dataset.columns, key=lambda c: c.position)]


@router.get("/{dataset_id}/quality", response_model=QualityReportOut)
def get_dataset_quality(dataset_id: UUID, db: Session = Depends(get_db)) -> QualityReportOut:
    dataset = _get_dataset_or_404(db, dataset_id)
    return QualityReportOut(
        dataset_id=dataset.id,
        quality_score=dataset.quality_score,
        issues=[QualityIssueOut.model_validate(i) for i in dataset.quality_issues],
    )


@router.get("/{dataset_id}/lineage", response_model=LineageOut)
def get_dataset_lineage(dataset_id: UUID, db: Session = Depends(get_db)) -> LineageOut:
    dataset = _get_dataset_or_404(db, dataset_id)
    return LineageOut(
        dataset_id=dataset.id,
        events=[LineageEventOut.model_validate(e) for e in dataset.lineage_events],
    )


@router.get("/{dataset_id}/preview", response_model=PreviewOut)
def get_dataset_preview(
    dataset_id: UUID, limit: int = 20, db: Session = Depends(get_db)
) -> PreviewOut:
    _get_dataset_or_404(db, dataset_id)  # 404 before touching the physical table
    columns, rows = service.get_preview(db, dataset_id, limit=limit)
    return PreviewOut(dataset_id=dataset_id, columns=columns, rows=rows)


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: UUID, db: Session = Depends(get_db)) -> None:
    _get_dataset_or_404(db, dataset_id)
    service.delete_dataset(db, dataset_id)
