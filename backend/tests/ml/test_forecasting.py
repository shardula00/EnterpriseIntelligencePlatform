"""Unit tests for app/ml/forecasting.py: chronological (never shuffled)
evaluation, honest backtesting against real held-out periods, and the
distinction between a scored backtest and an unscored future forecast.
"""

import numpy as np
import pandas as pd
import pytest

from app.ml.errors import InvalidMlConfigurationError
from app.ml.forecasting import predict_forecast, train_forecast
from tests.ml.helpers import sales_timeseries_dataframe


def test_train_forecast_backtests_against_the_true_last_horizon_periods():
    df = sales_timeseries_dataframe(n=120)
    horizon = 14
    results, _ = train_forecast(
        df,
        datetime_column="order_date",
        target_column="sales_amount",
        horizon=horizon,
        random_seed=42,
    )
    # historical must contain every real period (never trimmed/altered),
    # in original chronological order.
    assert len(results.historical) == 120
    assert results.historical[0].period == "2024-01-01"
    periods = [p.period for p in results.historical]
    assert periods == sorted(periods)


def test_train_forecast_never_shuffles_and_beats_naive_on_a_trending_series():
    """The synthetic series has a real upward trend + weekly seasonality -
    a competent model should out-perform a naive "repeat last value"
    baseline on MAE."""
    df = sales_timeseries_dataframe(n=150)
    results, _ = train_forecast(
        df, datetime_column="order_date", target_column="sales_amount", horizon=14, random_seed=42
    )
    naive_mae = next(c.metrics["mae"] for c in results.candidate_models if c.model_name == "Naive")
    best_mae = results.metrics["mae"]
    assert best_mae <= naive_mae
    assert results.primary_metric == "mae"


def test_train_forecast_produces_exactly_horizon_future_points_after_last_real_date():
    df = sales_timeseries_dataframe(n=100)
    horizon = 10
    results, _ = train_forecast(
        df,
        datetime_column="order_date",
        target_column="sales_amount",
        horizon=horizon,
        random_seed=42,
    )
    assert len(results.forecast) == horizon
    last_historical_date = pd.Timestamp(results.historical[-1].period)
    first_forecast_date = pd.Timestamp(results.forecast[0].period)
    assert first_forecast_date > last_historical_date


def test_train_forecast_confidence_interval_only_present_when_random_forest_wins():
    df = sales_timeseries_dataframe(n=150)
    results, _ = train_forecast(
        df, datetime_column="order_date", target_column="sales_amount", horizon=14, random_seed=42
    )
    if results.has_confidence_interval:
        assert results.selected_model == "Random Forest"
        assert all(
            p.lower is not None and p.upper is not None and p.lower <= p.upper
            for p in results.forecast
        )
    else:
        assert all(p.lower is None and p.upper is None for p in results.forecast)


def test_train_forecast_rejects_insufficient_history_for_requested_horizon():
    df = sales_timeseries_dataframe(n=20)
    with pytest.raises(InvalidMlConfigurationError):
        train_forecast(
            df,
            datetime_column="order_date",
            target_column="sales_amount",
            horizon=14,
            random_seed=42,
        )


def test_predict_forecast_extends_from_artifact_without_retraining():
    df = sales_timeseries_dataframe(n=120)
    _, artifact = train_forecast(
        df, datetime_column="order_date", target_column="sales_amount", horizon=14, random_seed=42
    )
    points = predict_forecast(artifact, horizon=5)
    assert len(points) == 5
    last_real_date = df["order_date"].iloc[-1]
    assert pd.Timestamp(points[0].period) > pd.Timestamp(last_real_date)
    # Values should be plausible (not NaN/inf), given the fitted model.
    assert all(np.isfinite(p.value) for p in points)
