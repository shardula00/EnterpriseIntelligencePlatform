"""Shared helpers for ML unit tests: build in-memory (never persisted to
the DB) Dataset/DatasetColumn objects and small synthetic DataFrames with a
known, hand-computable data-generating process, so tests assert on actual
expected behavior rather than "it didn't crash."
"""

import uuid

import numpy as np
import pandas as pd

from app.models.dataset import Dataset, DatasetColumn


def make_column(
    name: str,
    detected_type: str,
    *,
    position: int = 0,
    distinct_count: int = 10,
    null_count: int = 0,
) -> DatasetColumn:
    return DatasetColumn(
        dataset_id=uuid.uuid4(),
        position=position,
        original_name=name,
        column_name=name,
        detected_type=detected_type,
        nullable=null_count > 0,
        null_count=null_count,
        distinct_count=distinct_count,
    )


def make_dataset(row_count: int, columns: list[DatasetColumn]) -> Dataset:
    dataset = Dataset(
        id=uuid.uuid4(),
        name="test-dataset",
        original_filename="test.csv",
        file_type="csv",
        storage_schema="ingested",
        storage_table_name="ds_test",
        row_count=row_count,
        column_count=len(columns),
        quality_score=1.0,
    )
    dataset.columns = columns
    return dataset


def churn_dataframe(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Binary classification data with a known signal: high tenure lowers
    churn odds, many support tickets raises them."""
    rng = np.random.default_rng(seed)
    tenure_months = rng.integers(1, 60, n)
    support_tickets = rng.poisson(1.2, n)
    monthly_charges = rng.normal(60, 15, n)
    logit = -0.06 * tenure_months + 0.5 * support_tickets + rng.normal(0, 0.3, n)
    churned = rng.random(n) < 1 / (1 + np.exp(-logit))
    return pd.DataFrame(
        {
            "tenure_months": tenure_months,
            "support_tickets": support_tickets,
            "monthly_charges": monthly_charges,
            "churned": churned,
        }
    )


def churn_columns() -> list[DatasetColumn]:
    return [
        make_column("tenure_months", "integer", position=0, distinct_count=59),
        make_column("support_tickets", "integer", position=1, distinct_count=6),
        make_column("monthly_charges", "float", position=2, distinct_count=200),
        make_column("churned", "boolean", position=3, distinct_count=2),
    ]


def sales_timeseries_dataframe(n: int = 120, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    t = np.arange(n)
    values = 200 + 0.5 * t + 15 * np.sin(2 * np.pi * t / 7) + rng.normal(0, 3, n)
    return pd.DataFrame({"order_date": dates, "sales_amount": values})


def sales_columns() -> list[DatasetColumn]:
    return [
        make_column("order_date", "datetime", position=0, distinct_count=120),
        make_column("sales_amount", "float", position=1, distinct_count=120),
    ]


def segmentation_dataframe(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    group_a = pd.DataFrame({"income": rng.normal(100, 5, 40), "spend": rng.normal(20, 4, 40)})
    group_b = pd.DataFrame({"income": rng.normal(25, 5, 40), "spend": rng.normal(80, 4, 40)})
    return pd.concat([group_a, group_b], ignore_index=True)


def segmentation_columns() -> list[DatasetColumn]:
    return [
        make_column("income", "float", position=0, distinct_count=80),
        make_column("spend", "float", position=1, distinct_count=80),
    ]


def anomaly_dataframe(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    normal = pd.DataFrame({"amount": rng.normal(50, 10, 95), "distance": rng.normal(5, 2, 95)})
    anomalies = pd.DataFrame({"amount": rng.normal(500, 20, 5), "distance": rng.normal(80, 5, 5)})
    return pd.concat([normal, anomalies], ignore_index=True)


def anomaly_columns() -> list[DatasetColumn]:
    return [
        make_column("amount", "float", position=0, distinct_count=100),
        make_column("distance", "float", position=1, distinct_count=100),
    ]
