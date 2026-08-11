"""Per-column type detection and coercion.

Detection works off pandas' own dtype where pandas already parsed it
unambiguously (native int/float/bool/datetime columns), and falls back to
a coercion-ratio heuristic for object/string columns: if nearly every
non-null value in a column can be parsed as a number or a date, the column
is treated as that type. "Nearly every" (not "every") because real-world
exports routinely have a stray bad value in an otherwise-numeric column -
that's a data quality issue to flag (see quality.py), not a reason to
give up and call the whole column text.
"""

import warnings

import pandas as pd

# Fraction of non-null values that must successfully parse as numeric/datetime
# for a text column to be reclassified as that type.
TYPE_INFERENCE_THRESHOLD = 0.98

DETECTED_TYPES = ("integer", "float", "boolean", "datetime", "text")


def detect_column_type(series: pd.Series) -> str:
    """Detect one column's type. Returns one of DETECTED_TYPES."""
    non_null = series.dropna()
    if non_null.empty:
        # Nothing to infer from; quality.py separately flags this as
        # `empty_column`. Defaulting to "text" keeps the physical column
        # creatable without guessing.
        return "text"

    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    numeric = pd.to_numeric(non_null, errors="coerce")
    if numeric.notna().mean() >= TYPE_INFERENCE_THRESHOLD:
        parsed = numeric.dropna()
        if (parsed % 1 == 0).all():
            return "integer"
        return "float"

    # `errors="coerce"` means a bad guess here is expected and handled -
    # pandas' "could not infer format" warning is noise for our purposes.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        datetime_parsed = pd.to_datetime(non_null, errors="coerce")
    if datetime_parsed.notna().mean() >= TYPE_INFERENCE_THRESHOLD:
        return "datetime"

    return "text"


def detect_column_types(df: pd.DataFrame) -> dict[str, str]:
    """Detect the type of every column. Returns {column_name: detected_type}."""
    return {str(col): detect_column_type(df[col]) for col in df.columns}


def coerce_dataframe(
    df: pd.DataFrame, detected_types: dict[str, str]
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Coerce every column to its detected type.

    Returns the coerced DataFrame plus a per-column count of values that
    failed to coerce and were turned into nulls (i.e. previously non-null
    values that are null after this call) - this is the signal quality.py
    uses to flag `inconsistent_type` columns.
    """
    coerced = df.copy()
    coercion_null_counts: dict[str, int] = {}

    for column, detected_type in detected_types.items():
        original_null_count = int(coerced[column].isna().sum())

        if detected_type == "integer":
            numeric = pd.to_numeric(coerced[column], errors="coerce")
            coerced[column] = numeric.round().astype("Int64")
        elif detected_type == "float":
            coerced[column] = pd.to_numeric(coerced[column], errors="coerce").astype("float64")
        elif detected_type == "boolean":
            coerced[column] = coerced[column].astype("boolean")
        elif detected_type == "datetime":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                coerced[column] = pd.to_datetime(coerced[column], errors="coerce")
        else:  # text
            is_null = coerced[column].isna()
            stringified = coerced[column].astype(str).str.strip()
            coerced[column] = stringified.where(~is_null, coerced[column])

        new_null_count = int(coerced[column].isna().sum())
        introduced = new_null_count - original_null_count
        if introduced > 0:
            coercion_null_counts[column] = introduced

    return coerced, coercion_null_counts
