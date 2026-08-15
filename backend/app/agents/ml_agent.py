"""ML agent: dataset suitability + forecasting.

Wraps app.ml.service directly (get_dataset_suitability, train_forecast_run)
- the same functions GET /datasets/{id}/ml/suitability and
POST /ml/train/forecasting already call. Only forecasting is exposed here,
not classification/segmentation/anomaly detection: those need a specific
target/feature column selection a free-text question has no reliable way
to express, whereas a forecast only needs a datetime + target column,
which suitability's own suggestions already resolve deterministically (see
forecast() below). A deliberate, documented scoping choice, not an
oversight - see app/agents/__init__.py.

Training is synchronous, same as calling POST /ml/train/forecasting
directly - this agent adds no new async/job-queue infrastructure.
"""

import uuid

from sqlalchemy.orm import Session

from app.agents.base import AgentOutcome, ToolOutcome
from app.config import Settings
from app.ml.schemas import DatasetSuitabilityOut, ForecastTrainRequest, TaskSuitabilityOut
from app.ml.service import get_dataset_suitability, train_forecast_run
from app.models.user import User
from app.rbac.service import has_permission

_SUITABILITY_PERMISSION = "ml:read"
_FORECAST_PERMISSION = "ml:train"

_DEFAULT_HORIZON = 14

# A best-effort mapping from a handful of common phrasings to a rough
# horizon in forecast periods - deliberately simple (no general date-math),
# since the exact period length depends on the dataset's own row
# granularity (daily/weekly/monthly), which isn't known until after
# suitability has already identified the datetime column.
_HORIZON_HINTS: list[tuple[str, int]] = [
    ("next quarter", 13),
    ("next year", 52),
    ("next month", 4),
    ("next week", 1),
    ("quarter", 13),
    ("year", 52),
    ("month", 4),
    ("week", 1),
]


def _parse_horizon_hint(question: str) -> int | None:
    lowered = question.lower()
    for phrase, periods in _HORIZON_HINTS:
        if phrase in lowered:
            return periods
    return None


def _forecast_task(suitability: DatasetSuitabilityOut) -> TaskSuitabilityOut | None:
    return next((t for t in suitability.tasks if t.task_type == "forecasting"), None)


def check_suitability(db: Session, user: User, dataset_id: uuid.UUID) -> tuple[ToolOutcome, DatasetSuitabilityOut | None]:
    if not has_permission(user, _SUITABILITY_PERMISSION):
        return (
            ToolOutcome(
                tool="check_suitability",
                allowed=False,
                summary=f"You don't have permission ({_SUITABILITY_PERMISSION}) to check ML suitability.",
            ),
            None,
        )

    suitability = get_dataset_suitability(db, dataset_id)
    task = _forecast_task(suitability)
    if task is None or not task.suitable:
        reasons = "; ".join(task.reasons) if task else "forecasting is not a recognized task for this dataset."
        return (
            ToolOutcome(
                tool="check_suitability",
                allowed=True,
                summary=f"This dataset is not suitable for forecasting: {reasons}",
                data={"suitable": False},
            ),
            suitability,
        )

    return (
        ToolOutcome(
            tool="check_suitability",
            allowed=True,
            summary="Dataset is suitable for forecasting.",
            data={
                "suitable": True,
                "suggested_datetime_columns": task.suggested_datetime_columns,
                "suggested_target_columns": task.suggested_target_columns,
            },
        ),
        suitability,
    )


def forecast(
    db: Session,
    settings: Settings,
    user: User,
    question: str,
    dataset_id: uuid.UUID,
    task: TaskSuitabilityOut,
) -> ToolOutcome:
    if not has_permission(user, _FORECAST_PERMISSION):
        return ToolOutcome(
            tool="forecast",
            allowed=False,
            summary=f"You don't have permission ({_FORECAST_PERMISSION}) to train a forecast.",
        )
    if not task.suggested_datetime_columns or not task.suggested_target_columns:
        return ToolOutcome(
            tool="forecast",
            allowed=True,
            summary="Could not identify a datetime and a numeric target column to forecast.",
        )

    horizon = _parse_horizon_hint(question) or _DEFAULT_HORIZON
    request = ForecastTrainRequest(
        dataset_id=dataset_id,
        datetime_column=task.suggested_datetime_columns[0],
        target_column=task.suggested_target_columns[0],
        horizon=min(horizon, 180),
    )
    return _train_forecast(db, settings, user, request)


def _train_forecast(db: Session, settings: Settings, user: User, request: ForecastTrainRequest) -> ToolOutcome:
    run_result = train_forecast_run(db, settings, request, user.id)
    results = run_result.results
    forecast_points = results.get("forecast", [])
    trend = ""
    if forecast_points:
        first, last = forecast_points[0]["value"], forecast_points[-1]["value"]
        direction = "up" if last > first else "down" if last < first else "flat"
        trend = f", trending {direction} from {first:.2f} to {last:.2f}"

    summary = (
        f"Trained a {results['selected_model']} forecast for '{request.target_column}' "
        f"over the next {request.horizon} period(s){trend}."
    )
    return ToolOutcome(
        tool="forecast",
        allowed=True,
        summary=summary,
        data={
            "run_id": str(run_result.id),
            "task_type": run_result.task_type,
            "selected_model": results["selected_model"],
            "horizon": request.horizon,
            "has_confidence_interval": results.get("has_confidence_interval", False),
        },
    )


def run(
    db: Session, settings: Settings, user: User, question: str, dataset_id: uuid.UUID | None,
    context: dict,
) -> AgentOutcome:
    if dataset_id is None:
        return AgentOutcome(
            agent="ml",
            outcomes=[
                ToolOutcome(
                    tool="check_suitability",
                    allowed=True,
                    summary="A forecast needs a dataset to run against - none was specified.",
                )
            ],
        )

    # DatasetNotFoundError deliberately propagates uncaught - the API layer
    # maps it to a 404, same as every other dataset-scoped endpoint.
    suitability_outcome, suitability = check_suitability(db, user, dataset_id)

    outcomes = [suitability_outcome]
    if not suitability_outcome.allowed:
        return AgentOutcome(agent="ml", outcomes=outcomes)
    if not suitability_outcome.data or not suitability_outcome.data.get("suitable"):
        return AgentOutcome(agent="ml", outcomes=outcomes)

    task = _forecast_task(suitability)
    forecast_outcome = forecast(db, settings, user, question, dataset_id, task)
    outcomes.append(forecast_outcome)
    if forecast_outcome.allowed and forecast_outcome.data:
        context["ml_run_id"] = forecast_outcome.data["run_id"]

    return AgentOutcome(agent="ml", outcomes=outcomes)
