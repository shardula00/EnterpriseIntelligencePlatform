"""Orchestration layer for the analytics API - the only module
app/api/analytics.py calls. Ties together nl_parser, query_builder, and
sql_guard with AnalyticsQuery persistence.

Never raises for a question it couldn't understand or a query that failed
to execute - both become a persisted, returned AnalyticsQuery with
status="unsupported"/"error" instead (same "always return a result, never
a 500 for an expected failure mode" pattern app/rag/service.py's
run_query() uses). DatasetNotFoundError is the one exception that *does*
propagate, since app/api/analytics.py maps it onto a 404 the same way
app/api/datasets.py already does everywhere else.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.analytics.errors import UnsafeSqlError, UnsupportedQuestionError
from app.analytics.nl_parser import parse
from app.analytics.query_builder import build_query
from app.analytics.sql_guard import validate_select_only
from app.config import Settings
from app.ingestion import service as ingestion_service
from app.models.analytics import AnalyticsQuery
from app.models.dataset import Dataset

# Never surfaced to the client - see run_query()'s docstring and
# app/api/analytics.py: "do not expose internal errors" applies to
# execution failures the same way it does everywhere else in this app.
_GENERIC_ERROR_MESSAGE = "The analytics query could not be executed. Please try again."


def _to_jsonable(value: Any) -> Any:
    """Convert one result-row cell to a JSON-safe Python value - the same
    kind of native-type normalization app/ingestion/table_builder.py's
    `_to_native` does on the way *into* Postgres, mirrored here for values
    coming back *out* (Decimal from SUM/AVG over integer columns, date/
    datetime from a raw date_trunc bucket)."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def run_query(
    db: Session,
    settings: Settings,
    dataset_id: uuid.UUID,
    question: str,
    asked_by: uuid.UUID | None,
) -> AnalyticsQuery:
    """The full question -> parse -> build -> validate -> execute -> persist
    pipeline. Always returns a persisted AnalyticsQuery."""
    dataset = ingestion_service.get_dataset(db, dataset_id)
    columns = sorted(dataset.columns, key=lambda c: c.position)

    try:
        intent = parse(question, columns)
    except UnsupportedQuestionError as exc:
        return _persist(
            db, dataset, question, asked_by, status="unsupported", error_message=str(exc)
        )

    built = build_query(dataset, columns, intent, settings.analytics_max_result_rows)

    try:
        validate_select_only(built.sql_text, dataset.storage_table_name)
    except UnsafeSqlError:
        # Should be unreachable - query_builder can only ever construct one
        # of a fixed set of SELECT shapes - but if it ever is, the client
        # gets the same generic message as any other execution failure,
        # never the internal validation detail.
        return _persist(
            db, dataset, question, asked_by, status="error", error_message=_GENERIC_ERROR_MESSAGE
        )

    try:
        rows = db.connection().execute(built.statement).all()
    except SQLAlchemyError:
        db.rollback()
        return _persist(
            db, dataset, question, asked_by, status="error", error_message=_GENERIC_ERROR_MESSAGE
        )

    result_rows = [
        {col: _to_jsonable(value) for col, value in zip(built.result_columns, row, strict=True)}
        for row in rows
    ]
    return _persist(
        db,
        dataset,
        question,
        asked_by,
        status="answered",
        generated_sql=built.sql_text,
        intent=intent.kind,
        columns=built.result_columns,
        rows=result_rows,
    )


def _persist(
    db: Session,
    dataset: Dataset,
    question: str,
    asked_by: uuid.UUID | None,
    *,
    status: str,
    generated_sql: str | None = None,
    intent: str | None = None,
    error_message: str | None = None,
    columns: list[str] | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> AnalyticsQuery:
    record = AnalyticsQuery(
        dataset_id=dataset.id,
        asked_by=asked_by,
        question=question,
        generated_sql=generated_sql,
        intent=intent,
        status=status,
        error_message=error_message,
        columns=columns or [],
        rows=rows or [],
        row_count=len(rows) if rows else 0,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_query(db: Session, query_id: uuid.UUID) -> AnalyticsQuery | None:
    return db.get(AnalyticsQuery, query_id)


def list_queries(
    db: Session, dataset_id: uuid.UUID | None = None, limit: int = 50
) -> list[AnalyticsQuery]:
    stmt = select(AnalyticsQuery).order_by(AnalyticsQuery.created_at.desc()).limit(limit)
    if dataset_id is not None:
        stmt = stmt.where(AnalyticsQuery.dataset_id == dataset_id)
    return list(db.execute(stmt).scalars())
