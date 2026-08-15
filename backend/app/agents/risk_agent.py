"""Risk agent: deterministic risk/signal flagging.

Reads two kinds of *already-computed* signal, never generating anything
new: an ML forecast's own trend/confidence-interval data (from an MLRun
this same orchestration run may have just produced - see ml_agent.py) and
existing MonitoringEvent severities (Phase 6, via app.mlops.service).
Deliberately NOT Phase 11's Decision Intelligence: no recommendations, no
what-if scenario simulation, no human-in-the-loop approval workflow - just
"here is what in the data already looks notable," using fixed thresholds,
zero new statistics, zero LLM calls. See app/agents/__init__.py.
"""

import uuid

from sqlalchemy.orm import Session

from app.agents.base import AgentOutcome, RiskFlag, ToolOutcome, highest_severity
from app.ml.errors import MlRunNotFoundError
from app.ml.service import get_run
from app.mlops.service import list_model_versions, list_monitoring_events
from app.models.ml_run import MLRun
from app.models.user import User
from app.rbac.service import has_permission

_ASSESS_PERMISSION = "mlops:read"

# Fraction change in the forecast's value from its first to its last
# period - a real, if simple, trend signal, not a prediction of anything
# beyond what the forecast itself already says.
_TREND_WARNING_RATIO = 0.05
_TREND_CRITICAL_RATIO = 0.15

# Confidence-interval width (upper - lower) as a fraction of the forecast
# value - how much the model itself admits it doesn't know.
_CI_WARNING_RATIO = 0.30
_CI_CRITICAL_RATIO = 0.60

_MONITORING_EVENT_LOOKBACK = 5


def _flags_from_forecast(run: MLRun) -> list[RiskFlag]:
    if run.task_type != "forecasting":
        return []
    results = run.results
    forecast = results.get("forecast") or []
    if not forecast:
        return []

    flags: list[RiskFlag] = []
    first_value, last_value = forecast[0]["value"], forecast[-1]["value"]
    if first_value:
        change = (last_value - first_value) / abs(first_value)
        if change <= -_TREND_CRITICAL_RATIO:
            flags.append(
                RiskFlag(
                    "critical",
                    f"Forecast shows a sharp declining trend ({change:.0%}) over the horizon.",
                    "forecast_trend",
                )
            )
        elif change <= -_TREND_WARNING_RATIO:
            flags.append(
                RiskFlag(
                    "warning",
                    f"Forecast shows a declining trend ({change:.0%}) over the horizon.",
                    "forecast_trend",
                )
            )

    if results.get("has_confidence_interval"):
        widths = [
            (p["upper"] - p["lower"]) / abs(p["value"])
            for p in forecast
            if p.get("upper") is not None and p.get("lower") is not None and p.get("value")
        ]
        widest = max(widths, default=0.0)
        if widest >= _CI_CRITICAL_RATIO:
            flags.append(
                RiskFlag(
                    "critical",
                    f"Forecast uncertainty is very high (confidence interval spans "
                    f"{widest:.0%} of the predicted value).",
                    "forecast_uncertainty",
                )
            )
        elif widest >= _CI_WARNING_RATIO:
            flags.append(
                RiskFlag(
                    "warning",
                    f"Forecast uncertainty is elevated (confidence interval spans "
                    f"{widest:.0%} of the predicted value).",
                    "forecast_uncertainty",
                )
            )
    else:
        flags.append(
            RiskFlag(
                "info",
                "Confidence interval unavailable for this forecast - uncertainty is not quantified.",
                "forecast_uncertainty",
            )
        )
    return flags


def _flags_from_monitoring(db: Session, dataset_id: uuid.UUID) -> list[RiskFlag]:
    """Re-surfaces existing MonitoringEvent severities for any model
    version trained on this dataset - never recomputes drift/performance
    statistics itself (see app/mlops/drift.py and app/mlops/monitoring.py
    for where those are actually computed)."""
    versions = list_model_versions(db, dataset_id=dataset_id, task_type=None, status=None)
    flags: list[RiskFlag] = []
    for version in versions:
        events = list_monitoring_events(
            db, model_version_id=version.id, limit=_MONITORING_EVENT_LOOKBACK
        )
        for event in events:
            if event.severity in ("warning", "critical"):
                flags.append(RiskFlag(event.severity, event.summary, "monitoring_event"))
    return flags


def assess_risk(
    db: Session, user: User, dataset_id: uuid.UUID | None, ml_run_id: str | None
) -> ToolOutcome:
    if not has_permission(user, _ASSESS_PERMISSION):
        return ToolOutcome(
            tool="assess_risk",
            allowed=False,
            summary=f"You don't have permission ({_ASSESS_PERMISSION}) to view risk signals.",
        )

    flags: list[RiskFlag] = []
    if ml_run_id is not None:
        try:
            run = get_run(db, uuid.UUID(ml_run_id))
            flags.extend(_flags_from_forecast(run))
        except MlRunNotFoundError:
            pass  # the run this risk check was meant to follow up on is gone - not fatal
    if dataset_id is not None:
        flags.extend(_flags_from_monitoring(db, dataset_id))

    if not flags:
        flags = [RiskFlag("info", "No notable risk signals detected.", "none")]

    overall = highest_severity(flags)
    summary = " ".join(f"[{f.severity}] {f.message}" for f in flags)
    return ToolOutcome(
        tool="assess_risk",
        allowed=True,
        summary=summary,
        data={
            "overall_severity": overall,
            "flags": [{"severity": f.severity, "message": f.message, "source": f.source} for f in flags],
        },
    )


def run(db: Session, user: User, dataset_id: uuid.UUID | None, context: dict) -> AgentOutcome:
    ml_run_id = context.get("ml_run_id")
    return AgentOutcome(agent="risk", outcomes=[assess_risk(db, user, dataset_id, ml_run_id)])
