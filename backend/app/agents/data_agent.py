"""Data agent: read-only dataset discovery/inspection.

Wraps app.ingestion.service (list/get dataset) and app.bi.service (KPI
summary) - the exact same functions app/api/datasets.py and app/api/kpis.py
already call. No write tools (upload/delete) are exposed here: "upload a
dataset" doesn't fit a natural-language request shape (there is no file to
attach), so uploading stays the existing dedicated endpoint.
"""

import uuid

from sqlalchemy.orm import Session

from app.agents.base import AgentOutcome, ToolOutcome
from app.bi.service import get_kpi_summary
from app.ingestion.service import get_dataset, list_datasets
from app.models.user import User
from app.rbac.service import has_permission

_LIST_PERMISSION = "dataset:read"
_DESCRIBE_PERMISSION = "dataset:read"


def list_available_datasets(db: Session, user: User) -> ToolOutcome:
    if not has_permission(user, _LIST_PERMISSION):
        return ToolOutcome(
            tool="list_datasets",
            allowed=False,
            summary=f"You don't have permission ({_LIST_PERMISSION}) to list datasets.",
        )

    datasets = list_datasets(db, limit=50)
    if not datasets:
        return ToolOutcome(
            tool="list_datasets", allowed=True, summary="No datasets have been uploaded yet.",
            data={"datasets": []},
        )

    names = ", ".join(d.name for d in datasets[:10])
    summary = f"Found {len(datasets)} dataset(s): {names}."
    return ToolOutcome(
        tool="list_datasets",
        allowed=True,
        summary=summary,
        data={
            "datasets": [
                {"id": str(d.id), "name": d.name, "row_count": d.row_count} for d in datasets
            ]
        },
    )


def describe_dataset(db: Session, user: User, dataset_id: uuid.UUID) -> ToolOutcome:
    if not has_permission(user, _DESCRIBE_PERMISSION):
        return ToolOutcome(
            tool="describe_dataset",
            allowed=False,
            summary=f"You don't have permission ({_DESCRIBE_PERMISSION}) to view this dataset.",
        )

    dataset = get_dataset(db, dataset_id)
    kpis = get_kpi_summary(db, dataset_id)
    summary = (
        f"'{dataset.name}' has {dataset.row_count} rows and {dataset.column_count} columns "
        f"(quality score {dataset.quality_score:.1f}). "
        f"Numeric columns: {', '.join(kpis.numeric_columns) or 'none'}."
    )
    return ToolOutcome(
        tool="describe_dataset",
        allowed=True,
        summary=summary,
        data={
            "id": str(dataset.id),
            "name": dataset.name,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "quality_score": dataset.quality_score,
            "numeric_columns": kpis.numeric_columns,
            "suggested_breakdown_columns": kpis.suggested_breakdown_columns,
            "suggested_trend_columns": kpis.suggested_trend_columns,
        },
    )


def run(db: Session, user: User, dataset_id: uuid.UUID | None) -> AgentOutcome:
    outcome = describe_dataset(db, user, dataset_id) if dataset_id else list_available_datasets(db, user)
    return AgentOutcome(agent="data", outcomes=[outcome])
