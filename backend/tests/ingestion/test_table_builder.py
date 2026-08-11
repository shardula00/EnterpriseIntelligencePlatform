"""Pure unit tests for table_builder.py - no database required.

Table creation/insertion/drop themselves are exercised end-to-end by
tests/test_datasets_api.py against a live Postgres, since that's the part
that actually needs a database.
"""

import numpy as np
import pandas as pd
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Text

from app.ingestion.table_builder import (
    INGESTED_SCHEMA,
    build_dataset_table,
    dataframe_to_records,
)


def test_build_dataset_table_has_row_id_primary_key_plus_columns():
    table = build_dataset_table("ds_abc123", {"amount": "integer", "name": "text"})

    assert table.schema == INGESTED_SCHEMA
    assert table.name == "ds_abc123"
    column_names = [c.name for c in table.columns]
    assert column_names == ["_row_id", "amount", "name"]
    assert table.columns["_row_id"].primary_key


def test_build_dataset_table_maps_detected_types_to_sql_types():
    table = build_dataset_table(
        "ds_types",
        {
            "a": "integer",
            "b": "float",
            "c": "boolean",
            "d": "datetime",
            "e": "text",
        },
    )

    assert isinstance(table.columns["a"].type, BigInteger)
    assert isinstance(table.columns["b"].type, Float)
    assert isinstance(table.columns["c"].type, Boolean)
    assert isinstance(table.columns["d"].type, DateTime)
    assert isinstance(table.columns["e"].type, Text)


def test_dataframe_to_records_converts_numpy_scalars_to_native_python():
    df = pd.DataFrame(
        {"a": np.array([1, 2], dtype="int64"), "b": np.array([1.5, 2.5], dtype="float64")}
    )
    records = dataframe_to_records(df)

    assert records == [{"a": 1, "b": 1.5}, {"a": 2, "b": 2.5}]
    assert isinstance(records[0]["a"], int)
    assert isinstance(records[0]["b"], float)


def test_dataframe_to_records_converts_nan_and_na_to_none():
    df = pd.DataFrame({"a": pd.array([1, None], dtype="Int64"), "b": [1.0, float("nan")]})
    records = dataframe_to_records(df)

    assert records[1]["a"] is None
    assert records[1]["b"] is None


def test_dataframe_to_records_converts_timestamp_to_datetime():
    df = pd.DataFrame({"when": pd.to_datetime(["2024-01-01"])})
    records = dataframe_to_records(df)

    import datetime

    assert isinstance(records[0]["when"], datetime.datetime)
    assert not isinstance(records[0]["when"], pd.Timestamp)
