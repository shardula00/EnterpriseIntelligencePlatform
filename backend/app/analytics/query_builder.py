"""Compiles a ParsedIntent into a safe, read-only SQL query.

Reuses exactly the pattern app/bi/service.py (Phase 3's KPI engine) already
established: reconstruct a dataset's physical table via
ingestion.table_builder.build_dataset_table (allow-list-sanitized column
names, already validated at ingestion time - see app/ingestion/naming.py),
then build the query with SQLAlchemy Core (`select`/`func.sum`/`group_by`/
`order_by`/`limit`) - never a hand-assembled SQL string. There is no code
path here that can emit anything but a single SELECT: every `kind` this
module handles (see app/analytics/nl_parser.py) maps to exactly one
`select(...)` shape below, so the "generated SQL" is a byproduct of what
was safely built, not an untrusted string this code has to defend against.

The human-readable SQL text returned alongside the statement (for display
and for app/analytics/sql_guard.py's independent check) is rendered from
that same compiled statement with literal_binds=True - it is never itself
executed; the statement object is.
"""

from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.dialects import postgresql

from app.analytics.nl_parser import ParsedIntent
from app.ingestion.table_builder import build_dataset_table
from app.models.dataset import Dataset, DatasetColumn

_AGG_FUNCS = {
    "sum": func.sum,
    "avg": func.avg,
    "count": func.count,
    "min": func.min,
    "max": func.max,
}


@dataclass
class BuiltQuery:
    statement: Select
    sql_text: str
    result_columns: list[str]


def _render(stmt: Select) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def build_query(
    dataset: Dataset, columns: list[DatasetColumn], intent: ParsedIntent, max_rows: int
) -> BuiltQuery:
    column_map = {c.column_name: c.detected_type for c in columns}
    table = build_dataset_table(dataset.storage_table_name, column_map)

    if intent.kind == "total":
        if intent.aggregation == "count":
            expr = func.count().label("count")
        else:
            expr = _AGG_FUNCS[intent.aggregation](table.c[intent.metric_column]).label(
                intent.metric_column
            )
        # select_from(table) is explicit here because bare func.count() (no
        # column argument) has no table affiliation of its own for
        # SQLAlchemy to infer a FROM clause from - unlike the sum/avg/min/
        # max branch above, which already anchors to `table` via
        # table.c[metric_column]. Without it, "total" + "count" rendered as
        # `SELECT count(*) AS count` with no FROM clause at all, which
        # sql_guard.py then (correctly) rejected for not referencing the
        # dataset's table.
        stmt = select(expr).select_from(table)
        result_columns = [expr.name]

    elif intent.kind == "breakdown":
        group_col = table.c[intent.group_by_column].label(intent.group_by_column)
        if intent.aggregation == "count":
            value_expr = func.count().label("count")
        else:
            value_expr = _AGG_FUNCS[intent.aggregation](table.c[intent.metric_column]).label(
                intent.metric_column
            )
        stmt = (
            select(group_col, value_expr)
            .group_by(group_col)
            .order_by(value_expr.desc())
            .limit(max_rows)
        )
        result_columns = [group_col.name, value_expr.name]

    elif intent.kind == "top_n":
        group_col = table.c[intent.group_by_column].label(intent.group_by_column)
        value_expr = _AGG_FUNCS[intent.aggregation](table.c[intent.metric_column]).label(
            intent.metric_column
        )
        order = value_expr.desc() if intent.descending else value_expr.asc()
        limit = min(intent.limit or 1, max_rows)
        stmt = select(group_col, value_expr).group_by(group_col).order_by(order).limit(limit)
        result_columns = [group_col.name, value_expr.name]

    elif intent.kind == "trend":
        bucket = func.date_trunc(intent.granularity, table.c[intent.date_column]).label("period")
        value_expr = _AGG_FUNCS[intent.aggregation](table.c[intent.metric_column]).label(
            intent.metric_column
        )
        stmt = select(bucket, value_expr).group_by(bucket).order_by(bucket).limit(max_rows)
        result_columns = [bucket.name, value_expr.name]

    else:  # pragma: no cover - nl_parser.parse() never produces any other kind
        raise ValueError(f"Unknown intent kind: {intent.kind}")

    return BuiltQuery(statement=stmt, sql_text=_render(stmt), result_columns=result_columns)
