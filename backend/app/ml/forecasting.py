"""Numeric time-series forecasting.

Every split is chronological - never shuffled. Two baselines (naive,
seasonal-naive) are compared against RandomForestRegressor and
HistGradientBoostingRegressor using engineered calendar + lag features.
Multi-step-ahead prediction for the ML models is recursive: each step's
prediction feeds back in as a lag feature for the next step - the
standard, dependency-light way to get a tree model to forecast multiple
periods ahead without a dedicated time-series library (statsmodels,
prophet, ...).

Backtest evaluation: models are fit on all-but-the-last-`horizon` periods,
then asked to (recursively) predict exactly those held-out periods, which
are compared against the real values that already happened - a genuine
holdout, not a leak. The forecast actually shown to the user, in contrast,
extends *beyond* the dataset's real last date using a model refit on the
complete series - there is no ground truth for that yet, by definition, so
it is never scored, only displayed.

Primary metric: MAE (mean absolute error, in the target's own units - more
interpretable than RMSE for a business audience, and less dominated by a
single bad period than RMSE). RMSE is reported alongside it; MAPE only
when every actual test value is non-zero (otherwise it's mathematically
unstable and is omitted rather than reported as a misleading number).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error

from app.ml.errors import InvalidMlConfigurationError
from app.ml.evaluation import round_metrics
from app.ml.feature_engineering import extract_calendar_features
from app.ml.schemas import (
    CandidateModelMetrics,
    ForecastPointOut,
    ForecastResultsOut,
    TimeSeriesPointOut,
)

PRIMARY_METRIC = "mae"
LAGS = [1, 7]
SEASONAL_PERIOD = 7  # weekly seasonality assumption for daily-ish data


class ForecastArtifact:
    """Everything predict() needs to extend the forecast later without
    retraining: the fitted production model (refit on the complete series),
    the feature names it expects, and the known history to seed recursion."""

    def __init__(
        self, model, feature_names: list[str], history: pd.DataFrame, freq: str, model_name: str
    ):
        self.model = model
        self.feature_names = feature_names
        self.history = history  # columns: date, value - the full series
        self.freq = freq
        self.model_name = model_name


def _prepare_series(df: pd.DataFrame, datetime_column: str, target_column: str) -> pd.DataFrame:
    ts = df[[datetime_column, target_column]].dropna().copy()
    ts[datetime_column] = pd.to_datetime(ts[datetime_column])
    ts = ts.sort_values(datetime_column).reset_index(drop=True)
    return ts.rename(columns={datetime_column: "date", target_column: "value"})


def _infer_frequency(dates: pd.Series) -> str:
    diffs = dates.diff().dropna()
    if diffs.empty:
        return "D"
    median_days = diffs.median() / pd.Timedelta(days=1)
    if median_days <= 1.5:
        return "D"
    if median_days <= 9:
        return "W"
    return "MS"


def _feature_row(date: pd.Timestamp, time_index: int, recent_values: list[float]) -> dict:
    row = extract_calendar_features(pd.Series([date]), start_index=time_index).iloc[0].to_dict()
    for lag in LAGS:
        row[f"lag_{lag}"] = recent_values[-lag] if len(recent_values) >= lag else np.nan
    return row


def _build_training_frame(ts: pd.DataFrame) -> pd.DataFrame:
    """One engineered feature row per period in `ts`, plus the target. Rows
    at the start where a lag can't be computed (not enough prior history)
    are dropped."""
    rows = []
    for i in range(len(ts)):
        rows.append(_feature_row(ts["date"].iloc[i], i, list(ts["value"].iloc[:i])))
    features = pd.DataFrame(rows)
    features["target"] = ts["value"].values
    return features.dropna().reset_index(drop=True)


def _recursive_predict(
    model,
    feature_names: list[str],
    history_values: list[float],
    start_time_index: int,
    dates: list[pd.Timestamp],
) -> list[float]:
    values = list(history_values)
    predictions = []
    for step, date in enumerate(dates):
        row = _feature_row(date, start_time_index + step, values)
        X_row = pd.DataFrame([row])[feature_names]
        pred = float(model.predict(X_row)[0])
        predictions.append(pred)
        values.append(pred)
    return predictions


def _naive_forecast(history_values: list[float], horizon: int) -> list[float]:
    return [history_values[-1]] * horizon


def _seasonal_naive_forecast(history_values: list[float], horizon: int, period: int) -> list[float]:
    if len(history_values) < period:
        return _naive_forecast(history_values, horizon)
    last_cycle = history_values[-period:]
    return [last_cycle[i % period] for i in range(horizon)]


def _compute_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    metrics = {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": mean_squared_error(actual, predicted) ** 0.5,
    }
    if np.all(np.abs(actual) > 1e-9):
        metrics["mape"] = mean_absolute_percentage_error(actual, predicted)
    return round_metrics(metrics)


def _rf_interval(rf_model, X_row: pd.DataFrame) -> tuple[float, float]:
    """A per-step approximation, not a fully propagated multi-step interval:
    the spread across the Random Forest's individual trees' predictions for
    this one feature row. Documented as a simplification, not hidden.

    Individual trees are fit internally on plain arrays (RandomForest
    strips column names before delegating to them), so predicting on a
    DataFrame here would trigger a spurious "fitted without feature names"
    warning per tree - passing a bare numpy array avoids that noise.
    """
    X_array = X_row.to_numpy()
    tree_preds = np.array([tree.predict(X_array)[0] for tree in rf_model.estimators_])
    return float(np.percentile(tree_preds, 10)), float(np.percentile(tree_preds, 90))


def train_forecast(
    df: pd.DataFrame,
    *,
    datetime_column: str,
    target_column: str,
    horizon: int,
    random_seed: int,
) -> tuple[ForecastResultsOut, ForecastArtifact]:
    ts = _prepare_series(df, datetime_column, target_column)
    if len(ts) <= horizon + max(LAGS) + 5:
        raise InvalidMlConfigurationError(
            f"Not enough history ({len(ts)} rows) for a horizon of {horizon} "
            f"periods plus lag features - reduce the horizon or use a larger dataset."
        )

    freq = _infer_frequency(ts["date"])
    train_ts = ts.iloc[: len(ts) - horizon].reset_index(drop=True)
    test_ts = ts.iloc[len(ts) - horizon :].reset_index(drop=True)

    train_frame = _build_training_frame(train_ts)
    feature_names = [c for c in train_frame.columns if c != "target"]
    X_train, y_train = train_frame[feature_names], train_frame["target"]

    history_values = list(train_ts["value"])
    test_dates = list(test_ts["date"])
    actual = test_ts["value"].to_numpy()

    candidates: list[CandidateModelMetrics] = []
    fitted: dict[str, tuple[object, list[float]]] = {}

    naive_pred = _naive_forecast(history_values, horizon)
    candidates.append(
        CandidateModelMetrics(
            model_name="Naive", metrics=_compute_metrics(actual, np.array(naive_pred))
        )
    )
    fitted["Naive"] = (None, naive_pred)

    seasonal_pred = _seasonal_naive_forecast(history_values, horizon, SEASONAL_PERIOD)
    candidates.append(
        CandidateModelMetrics(
            model_name="Seasonal Naive", metrics=_compute_metrics(actual, np.array(seasonal_pred))
        )
    )
    fitted["Seasonal Naive"] = (None, seasonal_pred)

    ml_models = {
        "Random Forest": RandomForestRegressor(n_estimators=200, random_state=random_seed),
        "Gradient Boosting": HistGradientBoostingRegressor(random_state=random_seed),
    }
    for name, model in ml_models.items():
        model.fit(X_train, y_train)
        backtest_pred = _recursive_predict(
            model, feature_names, history_values, len(train_ts), test_dates
        )
        candidates.append(
            CandidateModelMetrics(
                model_name=name, metrics=_compute_metrics(actual, np.array(backtest_pred))
            )
        )
        fitted[name] = (model, backtest_pred)

    best_name = min(candidates, key=lambda c: c.metrics[PRIMARY_METRIC]).model_name
    best_metrics = next(c.metrics for c in candidates if c.model_name == best_name)

    # Refit the winning model type on the FULL series for the production
    # artifact and the forward-looking forecast - the backtest above is
    # what proves it works, this is what actually gets used going forward.
    full_frame = _build_training_frame(ts)
    X_full, y_full = full_frame[feature_names], full_frame["target"]
    all_history = list(ts["value"])
    future_dates = list(
        pd.date_range(start=ts["date"].iloc[-1], periods=horizon + 1, freq=freq)[1:]
    )

    if best_name in ml_models:
        production_model = type(ml_models[best_name])(**ml_models[best_name].get_params())
        production_model.fit(X_full, y_full)
        forecast_values = _recursive_predict(
            production_model, feature_names, all_history, len(ts), future_dates
        )
        has_interval = best_name == "Random Forest"
        intervals: list[tuple[float, float] | None] = []
        if has_interval:
            values_for_interval = list(all_history)
            for step, date in enumerate(future_dates):
                row = _feature_row(date, len(ts) + step, values_for_interval)
                X_row = pd.DataFrame([row])[feature_names]
                intervals.append(_rf_interval(production_model, X_row))
                values_for_interval.append(forecast_values[step])
        else:
            intervals = [None] * horizon
    else:
        production_model = best_name  # "Naive" or "Seasonal Naive" - no model object needed
        forecast_values = (
            _naive_forecast(all_history, horizon)
            if best_name == "Naive"
            else _seasonal_naive_forecast(all_history, horizon, SEASONAL_PERIOD)
        )
        has_interval = False
        intervals = [None] * horizon

    results = ForecastResultsOut(
        datetime_column=datetime_column,
        target_column=target_column,
        horizon=horizon,
        candidate_models=candidates,
        selected_model=best_name,
        primary_metric=PRIMARY_METRIC,
        metrics=best_metrics,
        historical=[
            TimeSeriesPointOut(period=d.date().isoformat(), value=float(v))
            for d, v in zip(ts["date"], ts["value"], strict=True)
        ],
        forecast=[
            ForecastPointOut(
                period=d.date().isoformat(),
                value=round(float(v), 4),
                lower=round(interval[0], 4) if interval else None,
                upper=round(interval[1], 4) if interval else None,
            )
            for d, v, interval in zip(future_dates, forecast_values, intervals, strict=True)
        ],
        has_confidence_interval=has_interval,
        random_seed=random_seed,
    )
    artifact = ForecastArtifact(
        model=production_model if best_name in ml_models else None,
        feature_names=feature_names,
        history=ts,
        freq=freq,
        model_name=best_name,
    )
    return results, artifact


def predict_forecast(artifact: ForecastArtifact, horizon: int) -> list[ForecastPointOut]:
    """Extend the forecast from an already-fitted artifact, optionally with
    a different horizon than the one used at training time."""
    all_history = list(artifact.history["value"])
    last_date = artifact.history["date"].iloc[-1]
    future_dates = list(pd.date_range(start=last_date, periods=horizon + 1, freq=artifact.freq)[1:])

    if artifact.model is None:
        values = (
            _naive_forecast(all_history, horizon)
            if artifact.model_name == "Naive"
            else _seasonal_naive_forecast(all_history, horizon, SEASONAL_PERIOD)
        )
        intervals = [None] * horizon
    else:
        values = _recursive_predict(
            artifact.model, artifact.feature_names, all_history, len(artifact.history), future_dates
        )
        intervals = [None] * horizon
        if artifact.model_name == "Random Forest":
            values_for_interval = list(all_history)
            intervals = []
            for step, date in enumerate(future_dates):
                row = _feature_row(date, len(artifact.history) + step, values_for_interval)
                X_row = pd.DataFrame([row])[artifact.feature_names]
                intervals.append(_rf_interval(artifact.model, X_row))
                values_for_interval.append(values[step])

    return [
        ForecastPointOut(
            period=d.date().isoformat(),
            value=round(float(v), 4),
            lower=round(interval[0], 4) if interval else None,
            upper=round(interval[1], 4) if interval else None,
        )
        for d, v, interval in zip(future_dates, values, intervals, strict=True)
    ]
