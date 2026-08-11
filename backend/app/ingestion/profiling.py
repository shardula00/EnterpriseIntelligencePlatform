"""Per-column statistics computed after type detection/coercion.

Profiling is intentionally simple (counts, min/max, mean, a few samples) -
enough for a data-quality picture and for a human to sanity-check a
dataset, without pulling in a full profiling library (e.g. ydata-profiling)
that this project's scale doesn't need.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

# Long text values are truncated before being stored, so a single huge
# cell can't inflate dataset_columns.min_value/max_value/sample_values.
MAX_STORED_VALUE_LENGTH = 200
MAX_SAMPLE_VALUES = 3


@dataclass
class ColumnProfile:
    column_name: str
    detected_type: str
    row_count: int
    null_count: int
    distinct_count: int
    min_value: str | None
    max_value: str | None
    mean_value: float | None
    sample_values: list[str]


def _stringify(value: Any) -> str:
    if isinstance(value, pd.Timestamp):
        value = value.isoformat()
    return str(value)[:MAX_STORED_VALUE_LENGTH]


def profile_column(series: pd.Series, detected_type: str) -> ColumnProfile:
    row_count = len(series)
    null_count = int(series.isna().sum())
    non_null = series.dropna()
    distinct_count = int(non_null.nunique())

    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None

    if not non_null.empty:
        if detected_type in ("integer", "float"):
            mean_value = float(non_null.astype("float64").mean())
            min_value = _stringify(non_null.min())
            max_value = _stringify(non_null.max())
        elif detected_type == "datetime":
            min_value = _stringify(non_null.min())
            max_value = _stringify(non_null.max())
        elif detected_type == "text":
            as_text = non_null.astype(str)
            min_value = _stringify(as_text.min())
            max_value = _stringify(as_text.max())
        # boolean: min/max/mean aren't meaningful enough to bother with.

    sample_values = [_stringify(v) for v in non_null.drop_duplicates().head(MAX_SAMPLE_VALUES)]

    return ColumnProfile(
        column_name=str(series.name),
        detected_type=detected_type,
        row_count=row_count,
        null_count=null_count,
        distinct_count=distinct_count,
        min_value=min_value,
        max_value=max_value,
        mean_value=mean_value,
        sample_values=sample_values,
    )


def profile_dataframe(df: pd.DataFrame, detected_types: dict[str, str]) -> list[ColumnProfile]:
    return [profile_column(df[col], detected_types[str(col)]) for col in df.columns]
