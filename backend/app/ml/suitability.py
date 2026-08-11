"""Generic, per-task dataset suitability checks.

Operates purely on already-computed Phase 2 metadata (Dataset.row_count,
DatasetColumn.detected_type/distinct_count) - no data loading needed for a
suitability check, which is what makes "can I even attempt this task on
this dataset" cheap enough to compute for all four tasks up front.

Two layers, deliberately separate:
  - `check_*` (this module's suitability functions) answer "is this
    dataset *structurally* capable of this task at all" - used to build
    the task-picker UI, never blocks a request by itself.
  - `validate_*_request` re-checks the *specific* columns a caller actually
    requested (they exist, they're the right type, the target isn't also a
    feature, ...) and raises InvalidMlConfigurationError with a specific
    reason - this is what actually gates a training request.
"""

from dataclasses import dataclass, field

from app.ml.errors import InvalidMlConfigurationError
from app.models.dataset import Dataset, DatasetColumn

NUMERIC_TYPES = {"integer", "float"}
CATEGORICAL_TYPES = {"text", "boolean"}

# Cardinality above this is treated as identifier-like, not categorical -
# excluded from automatic feature suggestions (a caller can still force it).
MAX_CATEGORICAL_CARDINALITY = 50

MIN_ROWS_CLASSIFICATION = 30
MIN_ROWS_FORECASTING = 30
MIN_ROWS_SEGMENTATION = 15
MIN_ROWS_ANOMALY = 15


@dataclass
class SuitabilityCheck:
    suitable: bool
    reasons: list[str]
    suggested_target_columns: list[str] = field(default_factory=list)
    suggested_datetime_columns: list[str] = field(default_factory=list)
    suggested_feature_columns: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Column suggestions - shared building blocks
# ---------------------------------------------------------------------------


def suggest_numeric_columns(columns: list[DatasetColumn]) -> list[str]:
    """Numeric columns with more than one distinct value (a constant numeric
    column carries no information for any ML task)."""
    return [
        c.column_name for c in columns if c.detected_type in NUMERIC_TYPES and c.distinct_count > 1
    ]


def suggest_datetime_columns(columns: list[DatasetColumn]) -> list[str]:
    return [c.column_name for c in columns if c.detected_type == "datetime"]


def suggest_binary_target_columns(columns: list[DatasetColumn]) -> list[str]:
    """Boolean columns, or text/integer columns with exactly two distinct
    values - both are legitimate binary targets."""
    result = []
    for c in columns:
        if c.detected_type == "boolean":
            result.append(c.column_name)
        elif c.detected_type in {"text", "integer"} and c.distinct_count == 2:
            result.append(c.column_name)
    return result


def suggest_feature_columns(columns: list[DatasetColumn], exclude: set[str]) -> list[str]:
    """Numeric columns (non-constant) plus low-cardinality categorical
    columns, excluding anything in `exclude` (typically the target). Datetime
    columns are never auto-suggested as plain features - forecasting handles
    them specially via calendar/lag feature extraction instead."""
    candidates = []
    for c in columns:
        if c.column_name in exclude or c.distinct_count <= 1:
            continue
        if c.detected_type in NUMERIC_TYPES:
            candidates.append(c.column_name)
        elif (
            c.detected_type in CATEGORICAL_TYPES and c.distinct_count <= MAX_CATEGORICAL_CARDINALITY
        ):
            candidates.append(c.column_name)
    return candidates


# ---------------------------------------------------------------------------
# Suitability checks
# ---------------------------------------------------------------------------


def check_classification(dataset: Dataset, columns: list[DatasetColumn]) -> SuitabilityCheck:
    reasons: list[str] = []
    targets = suggest_binary_target_columns(columns)

    if not targets:
        reasons.append(
            "Binary classification requires a target column with exactly two "
            "meaningful classes (a boolean column, or a text/integer column "
            "with exactly 2 distinct values) - none was found."
        )
    if dataset.row_count < MIN_ROWS_CLASSIFICATION:
        reasons.append(
            f"At least {MIN_ROWS_CLASSIFICATION} rows are recommended for a "
            f"meaningful train/test split; this dataset has {dataset.row_count}."
        )

    features = suggest_feature_columns(columns, exclude=set(targets))
    if targets and not features:
        reasons.append("No usable feature columns were found besides the target.")

    return SuitabilityCheck(
        suitable=len(reasons) == 0,
        reasons=reasons,
        suggested_target_columns=targets,
        suggested_feature_columns=features,
    )


def check_forecasting(dataset: Dataset, columns: list[DatasetColumn]) -> SuitabilityCheck:
    reasons: list[str] = []
    datetimes = suggest_datetime_columns(columns)
    numeric_targets = suggest_numeric_columns(columns)

    if not datetimes:
        reasons.append("Forecasting cannot be performed because no datetime column was detected.")
    if not numeric_targets:
        reasons.append(
            "Forecasting requires at least one non-constant numeric column to use as the target."
        )
    if dataset.row_count < MIN_ROWS_FORECASTING:
        reasons.append(
            f"At least {MIN_ROWS_FORECASTING} time-ordered rows are recommended "
            f"for a chronological train/test split; this dataset has {dataset.row_count}."
        )

    return SuitabilityCheck(
        suitable=len(reasons) == 0,
        reasons=reasons,
        suggested_datetime_columns=datetimes,
        suggested_target_columns=numeric_targets,
    )


def check_segmentation(dataset: Dataset, columns: list[DatasetColumn]) -> SuitabilityCheck:
    reasons: list[str] = []
    numeric = suggest_numeric_columns(columns)

    if len(numeric) < 2:
        reasons.append(
            f"Segmentation requires at least 2 non-constant numeric feature "
            f"columns to cluster on; found {len(numeric)}."
        )
    if dataset.row_count < MIN_ROWS_SEGMENTATION:
        reasons.append(
            f"At least {MIN_ROWS_SEGMENTATION} rows are recommended for "
            f"clustering; this dataset has {dataset.row_count}."
        )

    return SuitabilityCheck(
        suitable=len(reasons) == 0, reasons=reasons, suggested_feature_columns=numeric
    )


def check_anomaly(dataset: Dataset, columns: list[DatasetColumn]) -> SuitabilityCheck:
    reasons: list[str] = []
    numeric = suggest_numeric_columns(columns)

    if len(numeric) < 1:
        reasons.append(
            "Anomaly detection requires at least 1 non-constant numeric feature column; "
            "none were found."
        )
    if dataset.row_count < MIN_ROWS_ANOMALY:
        reasons.append(
            f"At least {MIN_ROWS_ANOMALY} rows are recommended for anomaly "
            f"detection; this dataset has {dataset.row_count}."
        )

    return SuitabilityCheck(
        suitable=len(reasons) == 0, reasons=reasons, suggested_feature_columns=numeric
    )


def check_all_tasks(dataset: Dataset, columns: list[DatasetColumn]) -> dict[str, SuitabilityCheck]:
    return {
        "classification": check_classification(dataset, columns),
        "forecasting": check_forecasting(dataset, columns),
        "segmentation": check_segmentation(dataset, columns),
        "anomaly_detection": check_anomaly(dataset, columns),
    }


# ---------------------------------------------------------------------------
# Per-request validation - what actually gates a training call
# ---------------------------------------------------------------------------


def validate_classification_request(
    columns: list[DatasetColumn], target_column: str, feature_columns: list[str] | None
) -> list[str]:
    by_name = {c.column_name: c for c in columns}
    if target_column not in by_name:
        raise InvalidMlConfigurationError(f"Unknown column '{target_column}'.")

    target = by_name[target_column]
    is_valid_binary = target.detected_type == "boolean" or (
        target.detected_type in {"text", "integer"} and target.distinct_count == 2
    )
    if not is_valid_binary:
        raise InvalidMlConfigurationError(
            f"Column '{target_column}' does not have exactly two meaningful "
            f"classes (detected type '{target.detected_type}', "
            f"{target.distinct_count} distinct values)."
        )

    return _resolve_feature_columns(columns, by_name, target_column, feature_columns)


def validate_forecast_request(
    columns: list[DatasetColumn], datetime_column: str, target_column: str
) -> None:
    by_name = {c.column_name: c for c in columns}
    if datetime_column not in by_name:
        raise InvalidMlConfigurationError(f"Unknown column '{datetime_column}'.")
    if by_name[datetime_column].detected_type != "datetime":
        raise InvalidMlConfigurationError(f"Column '{datetime_column}' is not a datetime column.")
    if target_column not in by_name:
        raise InvalidMlConfigurationError(f"Unknown column '{target_column}'.")
    if by_name[target_column].detected_type not in NUMERIC_TYPES:
        raise InvalidMlConfigurationError(f"Column '{target_column}' is not numeric.")
    if target_column == datetime_column:
        raise InvalidMlConfigurationError(
            "The target column and datetime column must be different."
        )


def validate_segmentation_request(
    columns: list[DatasetColumn], feature_columns: list[str] | None
) -> list[str]:
    by_name = {c.column_name: c for c in columns}
    resolved = feature_columns if feature_columns is not None else suggest_numeric_columns(columns)

    unknown = set(resolved) - set(by_name)
    if unknown:
        raise InvalidMlConfigurationError(
            f"Unknown feature column(s): {', '.join(sorted(unknown))}."
        )
    non_numeric = [name for name in resolved if by_name[name].detected_type not in NUMERIC_TYPES]
    if non_numeric:
        raise InvalidMlConfigurationError(
            f"Segmentation features must be numeric; not numeric: {', '.join(sorted(non_numeric))}."
        )
    if len(resolved) < 2:
        raise InvalidMlConfigurationError("Segmentation requires at least 2 feature columns.")
    return resolved


def validate_anomaly_request(
    columns: list[DatasetColumn], feature_columns: list[str] | None
) -> list[str]:
    by_name = {c.column_name: c for c in columns}
    resolved = feature_columns if feature_columns is not None else suggest_numeric_columns(columns)

    unknown = set(resolved) - set(by_name)
    if unknown:
        raise InvalidMlConfigurationError(
            f"Unknown feature column(s): {', '.join(sorted(unknown))}."
        )
    non_numeric = [name for name in resolved if by_name[name].detected_type not in NUMERIC_TYPES]
    if non_numeric:
        raise InvalidMlConfigurationError(
            f"Anomaly detection features must be numeric; "
            f"not numeric: {', '.join(sorted(non_numeric))}."
        )
    if len(resolved) < 1:
        raise InvalidMlConfigurationError("Anomaly detection requires at least 1 feature column.")
    return resolved


def _resolve_feature_columns(
    columns: list[DatasetColumn],
    by_name: dict[str, DatasetColumn],
    target_column: str,
    feature_columns: list[str] | None,
) -> list[str]:
    if feature_columns is None:
        resolved = suggest_feature_columns(columns, exclude={target_column})
    else:
        unknown = set(feature_columns) - set(by_name)
        if unknown:
            raise InvalidMlConfigurationError(
            f"Unknown feature column(s): {', '.join(sorted(unknown))}."
        )
        if target_column in feature_columns:
            raise InvalidMlConfigurationError("The target column cannot also be a feature column.")
        resolved = feature_columns

    if not resolved:
        raise InvalidMlConfigurationError("No usable feature columns available.")
    return resolved
