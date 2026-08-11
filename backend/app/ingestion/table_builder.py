"""Builds and manages the one physical Postgres table each uploaded dataset
gets, in the dedicated `ingested` schema.

Tables are always built as SQLAlchemy `Table`/`Column` objects and never as
hand-written DDL strings - the SQL compiler is responsible for correctly
quoting identifiers, and (combined with naming.sanitize_identifier already
restricting those identifiers to `[a-z0-9_]`) that's what makes dynamic,
per-upload table creation safe against injection.

These tables are intentionally NOT part of `app.db.Base.metadata` - they're
runtime-created, one per upload, and Alembic never needs to know about them
(see migrations/env.py, which only tracks the fixed app_metadata/datasets/
dataset_columns/... tables).
"""

from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Identity,
    MetaData,
    Table,
    Text,
    select,
)
from sqlalchemy.engine import Connection

INGESTED_SCHEMA = "ingested"

_TYPE_MAP: dict[str, Any] = {
    "integer": BigInteger,
    "float": Float,
    "boolean": Boolean,
    "datetime": DateTime,
    "text": Text,
}


def build_dataset_table(table_name: str, columns: dict[str, str]) -> Table:
    """Construct (but do not create) the Table for a dataset's data.

    `columns` maps sanitized column_name -> detected_type. A fresh
    MetaData() is used per call since these tables are independent of each
    other and of the app's declarative Base.
    """
    metadata = MetaData(schema=INGESTED_SCHEMA)
    table_columns: list[Column] = [Column("_row_id", BigInteger, Identity(), primary_key=True)]
    for name, detected_type in columns.items():
        table_columns.append(Column(name, _TYPE_MAP[detected_type]))
    return Table(table_name, metadata, *table_columns)


def _to_native(value: Any) -> Any:
    """Convert one DataFrame cell to a type psycopg can bind directly."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, np.generic):
        return value.item()
    return value


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame into a list of dicts of native Python values.

    Needed because pandas/numpy scalar types (np.int64, np.float64,
    pd.Timestamp, pd.NA, NaN, NaT) aren't all directly bindable by the DB
    driver - everything is normalized to plain int/float/str/bool/datetime/
    None first.
    """
    columns = [str(c) for c in df.columns]
    return [
        dict(zip(columns, (_to_native(v) for v in row), strict=True))
        for row in df.itertuples(index=False, name=None)
    ]


def create_and_load(connection: Connection, table: Table, records: list[dict[str, Any]]) -> None:
    """Create the physical table and bulk-insert its rows."""
    table.metadata.create_all(bind=connection, tables=[table])
    if records:
        connection.execute(table.insert(), records)


def fetch_preview_rows(connection: Connection, table: Table, limit: int) -> list[dict[str, Any]]:
    """Read up to `limit` rows back from a dataset's physical table."""
    result = connection.execute(select(table).limit(limit))
    return [dict(row._mapping) for row in result]


def drop_dataset_table(connection: Connection, table_name: str) -> None:
    """Drop a dataset's physical table, if it exists."""
    metadata = MetaData(schema=INGESTED_SCHEMA)
    table = Table(table_name, metadata)
    table.drop(bind=connection, checkfirst=True)
