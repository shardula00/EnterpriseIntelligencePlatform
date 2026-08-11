"""Loads a dataset's full physical table into a pandas DataFrame.

Reuses ingestion.table_builder (the same safe, sanitized table
reconstruction Phase 2 already validated) rather than a second
ingestion/data-access path - see app/ml/__init__.py.
"""

import pandas as pd
from sqlalchemy.orm import Session

from app.ingestion.table_builder import build_dataset_table, fetch_preview_rows
from app.models.dataset import Dataset


def load_dataset_dataframe(db: Session, dataset: Dataset) -> pd.DataFrame:
    """Load every row of `dataset`'s physical table, in column order,
    excluding the internal `_row_id` primary key."""
    ordered_columns = sorted(dataset.columns, key=lambda c: c.position)
    column_map = {c.column_name: c.detected_type for c in ordered_columns}
    table = build_dataset_table(dataset.storage_table_name, column_map)

    # +1 margin costs nothing and tolerates row_count being very slightly
    # stale relative to the physical table.
    rows = fetch_preview_rows(db.connection(), table, limit=dataset.row_count + 1)
    # `str(k)`, not just `k`: SQLAlchemy's RowMapping keys are `quoted_name`
    # (a str subclass), which is indistinguishable from a plain str for
    # every other caller of fetch_preview_rows (JSON serialization doesn't
    # care) but trips up scikit-learn's column-name detection, which checks
    # `type(name) is str` exactly - a DataFrame built from quoted_name keys
    # silently loses its column names deep inside ColumnTransformer.
    return pd.DataFrame([{str(k): v for k, v in row.items() if k != "_row_id"} for row in rows])


def downsample_if_needed(
    df: pd.DataFrame, max_rows: int, random_seed: int
) -> tuple[pd.DataFrame, bool]:
    """Cap training data at `max_rows` (a local-student-project safety
    limit, not a silent one - the caller is expected to record `was_sampled`
    in the run's configuration so nobody is misled about what was trained
    on)."""
    if len(df) <= max_rows:
        return df, False
    return df.sample(n=max_rows, random_state=random_seed).reset_index(drop=True), True
