"""KPI API: generic aggregate/breakdown/trend computation over a dataset.

Thin HTTP layer only - all computation lives in app/bi/service.py.

Permission split (Phase 4): the plain summary (stat tiles) only needs
dashboard:read, but choosing breakdown/trend parameters is treated as
"configuring" the dashboard and needs dashboard:configure - see
ARCHITECTURE.md for the reasoning.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.bi import service
from app.bi.errors import InvalidKpiRequestError
from app.bi.schemas import (
    BreakdownItemOut,
    BreakdownOut,
    KpiSummaryOut,
    KpiValueOut,
    TrendOut,
    TrendPointOut,
)
from app.db import get_db
from app.ingestion.errors import DatasetNotFoundError
from app.models.user import User
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/datasets", tags=["kpis"])


@router.get("/{dataset_id}/kpis", response_model=KpiSummaryOut)
def get_kpi_summary(
    dataset_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("dashboard:read")),
) -> KpiSummaryOut:
    try:
        summary = service.get_kpi_summary(db, dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return KpiSummaryOut(
        dataset_id=dataset_id,
        kpis=[KpiValueOut(column=k.column, kind=k.kind, value=k.value) for k in summary.kpis],
        numeric_columns=summary.numeric_columns,
        suggested_breakdown_columns=summary.suggested_breakdown_columns,
        suggested_trend_columns=summary.suggested_trend_columns,
    )


@router.get("/{dataset_id}/kpis/breakdown", response_model=BreakdownOut)
def get_breakdown(
    dataset_id: UUID,
    group_by: str,
    metric: str | None = None,
    agg: str = "sum",
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("dashboard:configure")),
) -> BreakdownOut:
    try:
        result = service.get_breakdown(db, dataset_id, group_by, metric, agg)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidKpiRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BreakdownOut(
        dataset_id=dataset_id,
        group_by=result.group_by,
        metric=result.metric,
        aggregation=result.aggregation,
        items=[BreakdownItemOut(category=i.category, value=i.value) for i in result.items],
        total_categories=result.total_categories,
    )


@router.get("/{dataset_id}/kpis/trend", response_model=TrendOut)
def get_trend(
    dataset_id: UUID,
    date_column: str,
    metric: str,
    granularity: str = "month",
    agg: str = "sum",
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("dashboard:configure")),
) -> TrendOut:
    try:
        result = service.get_trend(db, dataset_id, date_column, metric, granularity, agg)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidKpiRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TrendOut(
        dataset_id=dataset_id,
        date_column=result.date_column,
        metric=result.metric,
        granularity=result.granularity,
        aggregation=result.aggregation,
        points=[TrendPointOut(period=p.period, value=p.value) for p in result.points],
    )
