"""Generic KPI computation.

Every KPI here is derived from a dataset's *actual* detected schema
(app/models/dataset.py: DatasetColumn.detected_type/distinct_count), not
from any hardcoded business column name:

- every numeric column gets sum/average/min/max stat tiles
- every low-cardinality text/boolean column becomes a candidate breakdown
  dimension (GROUP BY)
- every datetime column becomes a candidate trend axis (date_trunc)

Queries run against the dataset's real physical table, reconstructed via
ingestion.table_builder.build_dataset_table - the same safe, allow-list-
sanitized column names Phase 2 already validated, so no new identifier
safety work is needed here.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bi.errors import InvalidKpiRequestError
from app.ingestion import service as ingestion_service
from app.ingestion.table_builder import build_dataset_table
from app.models.dataset import DatasetColumn

NUMERIC_TYPES = {"integer", "float"}
BREAKDOWN_CANDIDATE_TYPES = {"text", "boolean"}
MAX_BREAKDOWN_CANDIDATE_DISTINCT = 20

STAT_KINDS = ("sum", "average", "min", "max")
_AGG_FUNCS = {
    "sum": func.sum,
    "average": func.avg,
    "min": func.min,
    "max": func.max,
    "count": func.count,
}
GRANULARITIES = ("day", "week", "month")
# dataviz guidance: cap categorical series, fold the rest into "Other"
BREAKDOWN_MAX_CATEGORIES = 8


@dataclass
class KpiValue:
    column: str
    kind: str  # one of STAT_KINDS
    value: float | None


@dataclass
class KpiSummary:
    kpis: list[KpiValue]
    numeric_columns: list[str]
    suggested_breakdown_columns: list[str]
    suggested_trend_columns: list[str]


@dataclass
class BreakdownItem:
    category: str
    value: float


@dataclass
class BreakdownResult:
    group_by: str
    metric: str | None
    aggregation: str
    items: list[BreakdownItem]
    total_categories: int


@dataclass
class TrendPoint:
    period: str
    value: float


@dataclass
class TrendResult:
    date_column: str
    metric: str
    granularity: str
    aggregation: str
    points: list[TrendPoint]


def _numeric_columns(columns: list[DatasetColumn]) -> list[DatasetColumn]:
    return [c for c in columns if c.detected_type in NUMERIC_TYPES]


def suggested_breakdown_columns(columns: list[DatasetColumn], row_count: int) -> list[str]:
    """Text/boolean columns worth grouping by.

    Beyond the absolute cap (MAX_BREAKDOWN_CANDIDATE_DISTINCT), a column is
    only useful to group by if categories actually group *multiple* rows -
    a column with one distinct value per row (e.g. customer_name on a
    per-order table) technically clears a small absolute cap but produces
    a "breakdown" that's just the raw rows relabeled, not an aggregation.
    Requiring the average category to cover >= 2 rows filters that out.
    """
    max_distinct = min(MAX_BREAKDOWN_CANDIDATE_DISTINCT, max(2, row_count // 2))
    return [
        c.column_name
        for c in columns
        if c.detected_type in BREAKDOWN_CANDIDATE_TYPES and 1 < c.distinct_count <= max_distinct
    ]


def suggested_trend_columns(columns: list[DatasetColumn]) -> list[str]:
    return [c.column_name for c in columns if c.detected_type == "datetime"]


def _ordered_columns(db: Session, dataset_id: UUID):
    """Fetch the dataset and its columns, ordered - raises DatasetNotFoundError."""
    dataset = ingestion_service.get_dataset(db, dataset_id)
    columns = sorted(dataset.columns, key=lambda c: c.position)
    return dataset, columns


def get_kpi_summary(db: Session, dataset_id: UUID) -> KpiSummary:
    dataset, columns = _ordered_columns(db, dataset_id)
    numeric_cols = _numeric_columns(columns)

    kpis: list[KpiValue] = []
    if numeric_cols:
        column_map = {c.column_name: c.detected_type for c in columns}
        table = build_dataset_table(dataset.storage_table_name, column_map)

        select_exprs = []
        for c in numeric_cols:
            sql_col = table.c[c.column_name]
            for kind in STAT_KINDS:
                select_exprs.append(_AGG_FUNCS[kind](sql_col).label(f"{c.column_name}__{kind}"))

        row = db.connection().execute(select(*select_exprs)).one()
        row_map = row._mapping
        for c in numeric_cols:
            for kind in STAT_KINDS:
                raw_value = row_map[f"{c.column_name}__{kind}"]
                value = float(raw_value) if raw_value is not None else None
                kpis.append(KpiValue(column=c.column_name, kind=kind, value=value))

    return KpiSummary(
        kpis=kpis,
        numeric_columns=[c.column_name for c in numeric_cols],
        suggested_breakdown_columns=suggested_breakdown_columns(columns, dataset.row_count),
        suggested_trend_columns=suggested_trend_columns(columns),
    )


def get_breakdown(
    db: Session, dataset_id: UUID, group_by: str, metric: str | None, aggregation: str
) -> BreakdownResult:
    dataset, columns = _ordered_columns(db, dataset_id)
    column_map = {c.column_name: c.detected_type for c in columns}

    if group_by not in column_map:
        raise InvalidKpiRequestError(f"Unknown column '{group_by}'.")
    if aggregation not in _AGG_FUNCS:
        raise InvalidKpiRequestError(f"Unknown aggregation '{aggregation}'.")
    if aggregation != "count":
        if metric is None:
            raise InvalidKpiRequestError("A 'metric' column is required for this aggregation.")
        if metric not in column_map:
            raise InvalidKpiRequestError(f"Unknown column '{metric}'.")
        if column_map[metric] not in NUMERIC_TYPES:
            raise InvalidKpiRequestError(f"Column '{metric}' is not numeric.")

    table = build_dataset_table(dataset.storage_table_name, column_map)
    group_col = table.c[group_by]
    if aggregation == "count":
        value_expr = _AGG_FUNCS["count"](group_col)
    else:
        value_expr = _AGG_FUNCS[aggregation](table.c[metric])

    connection = db.connection()
    distinct_count_stmt = select(func.count(func.distinct(group_col)))
    total_categories = connection.execute(distinct_count_stmt).scalar() or 0

    stmt = (
        select(group_col.label("category"), value_expr.label("value"))
        .group_by(group_col)
        .order_by(value_expr.desc())
        .limit(BREAKDOWN_MAX_CATEGORIES)
    )
    rows = connection.execute(stmt).all()

    items = [
        BreakdownItem(
            category="(empty)" if r.category is None else str(r.category),
            value=float(r.value or 0),
        )
        for r in rows
    ]
    return BreakdownResult(
        group_by=group_by,
        metric=metric,
        aggregation=aggregation,
        items=items,
        total_categories=total_categories,
    )


def get_trend(
    db: Session, dataset_id: UUID, date_column: str, metric: str, granularity: str, aggregation: str
) -> TrendResult:
    dataset, columns = _ordered_columns(db, dataset_id)
    column_map = {c.column_name: c.detected_type for c in columns}

    if date_column not in column_map:
        raise InvalidKpiRequestError(f"Unknown column '{date_column}'.")
    if column_map[date_column] != "datetime":
        raise InvalidKpiRequestError(f"Column '{date_column}' is not a datetime column.")
    if metric not in column_map:
        raise InvalidKpiRequestError(f"Unknown column '{metric}'.")
    if aggregation != "count" and column_map[metric] not in NUMERIC_TYPES:
        raise InvalidKpiRequestError(f"Column '{metric}' is not numeric.")
    if aggregation not in _AGG_FUNCS:
        raise InvalidKpiRequestError(f"Unknown aggregation '{aggregation}'.")
    if granularity not in GRANULARITIES:
        raise InvalidKpiRequestError(f"Unknown granularity '{granularity}'.")

    table = build_dataset_table(dataset.storage_table_name, column_map)
    date_col = table.c[date_column]
    bucket = func.date_trunc(granularity, date_col).label("bucket")
    value_expr = _AGG_FUNCS[aggregation](table.c[metric])

    stmt = select(bucket, value_expr.label("value")).group_by(bucket).order_by(bucket)
    rows = db.connection().execute(stmt).all()

    points = [
        TrendPoint(period=r.bucket.date().isoformat(), value=float(r.value or 0))
        for r in rows
        if r.bucket is not None
    ]
    return TrendResult(
        date_column=date_column,
        metric=metric,
        granularity=granularity,
        aggregation=aggregation,
        points=points,
    )
