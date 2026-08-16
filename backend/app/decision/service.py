"""Orchestration layer for Decision Intelligence - the only module
app/api/decisions.py and app/agents/decision_agent.py call directly.

`propose_recommendation()` reuses Phase 10's ML/Risk output two ways:
if it's called *within* a live agent orchestration run (an ML/Risk agent
already ran earlier in the same POST /agents/run request), it reads their
ToolOutcome objects directly via `prior_outcomes`. Called standalone
(POST /decisions, with no live orchestration context), it instead falls
back to the dataset's most recent forecasting run plus a fresh
app.agents.risk_agent.assess_risk() call against it - reusing that
function exactly as it already exists, never re-implementing risk
flagging here. Either way, this module never invents ML/Risk output of
its own.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import risk_agent
from app.agents.base import AgentOutcome, ToolOutcome
from app.config import Settings
from app.decision import recommendation as recommendation_composer
from app.decision import scenario as scenario_engine
from app.decision.errors import InvalidDecisionActionError, RecommendationNotFoundError
from app.ingestion import service as ingestion_service
from app.ml import service as ml_service
from app.models.decision import Recommendation
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _find_tool_outcome(
    agent_outcomes: list[AgentOutcome] | None, agent_name: str, tool_name: str
) -> ToolOutcome | None:
    if not agent_outcomes:
        return None
    for agent_outcome in agent_outcomes:
        if agent_outcome.agent != agent_name:
            continue
        for outcome in agent_outcome.outcomes:
            if outcome.tool == tool_name and outcome.allowed:
                return outcome
    return None


def _fallback_ml_and_risk_outcomes(
    db: Session, user: User, dataset_id: uuid.UUID
) -> tuple[ToolOutcome | None, ToolOutcome | None]:
    """No live orchestration context was given - reuse the dataset's most
    recent forecasting run (if any) and a fresh risk read of it, via the
    exact same app.ml.service/app.agents.risk_agent functions the agents
    themselves call. Never re-implements either."""
    runs = ml_service.list_runs(db, dataset_id=dataset_id, task_type="forecasting", limit=1)
    if not runs:
        return None, None
    latest_run = runs[0]
    ml_outcome = ToolOutcome(
        tool="forecast",
        allowed=True,
        summary=f"Using the most recent forecast run for this dataset ({latest_run.model_name}).",
        data={
            "run_id": str(latest_run.id),
            "task_type": latest_run.task_type,
            "selected_model": latest_run.model_name,
            "has_confidence_interval": latest_run.results.get("has_confidence_interval", False),
        },
    )
    risk_outcome = risk_agent.assess_risk(db, user, dataset_id, ml_run_id=str(latest_run.id))
    return ml_outcome, risk_outcome


def propose_recommendation(
    db: Session,
    settings: Settings,
    user: User,
    dataset_id: uuid.UUID,
    question: str,
    prior_outcomes: list[AgentOutcome] | None = None,
) -> Recommendation:
    """Raises DatasetNotFoundError (app.ingestion.errors) if the dataset
    doesn't exist - the same error every other dataset-scoped endpoint
    already maps to a 404 with."""
    dataset = ingestion_service.get_dataset(db, dataset_id)
    columns = sorted(dataset.columns, key=lambda c: c.position)

    ml_outcome = _find_tool_outcome(prior_outcomes, "ml", "forecast")
    risk_outcome = _find_tool_outcome(prior_outcomes, "risk", "assess_risk")
    if ml_outcome is None and risk_outcome is None:
        ml_outcome, risk_outcome = _fallback_ml_and_risk_outcomes(db, user, dataset_id)

    scenario_result = scenario_engine.run_scenario(db, settings, dataset, columns, question)

    composed = recommendation_composer.compose(ml_outcome, risk_outcome, scenario_result)

    evidence = []
    if ml_outcome is not None:
        evidence.append(
            {"agent": "ml", "tool": ml_outcome.tool, "summary": ml_outcome.summary, "data": ml_outcome.data}
        )
    if risk_outcome is not None:
        evidence.append(
            {
                "agent": "risk",
                "tool": risk_outcome.tool,
                "summary": risk_outcome.summary,
                "data": risk_outcome.data,
            }
        )

    risks = []
    if risk_outcome is not None and risk_outcome.data:
        risks = risk_outcome.data.get("flags", [])

    expected_impact = None
    if scenario_result.computed:
        expected_impact = {
            "affected_metric": scenario_result.affected_metric,
            "perturbed_metric": scenario_result.perturbed_metric,
            "delta_percent": scenario_result.delta_percent,
            "baseline_perturbed_value": scenario_result.baseline_perturbed_value,
            "baseline_affected_value": scenario_result.baseline_affected_value,
            "new_perturbed_value": scenario_result.new_perturbed_value,
            "new_affected_value": scenario_result.new_affected_value,
            "affected_value_change": scenario_result.affected_value_change,
            "relationship": scenario_result.relationship,
            "note": scenario_result.note,
        }

    record = Recommendation(
        dataset_id=dataset.id,
        created_by=user.id,
        question=question,
        recommendation=composed.text,
        alternatives=composed.alternatives,
        evidence=evidence,
        risks=risks,
        assumptions=composed.assumptions,
        confidence=composed.confidence,
        expected_impact=expected_impact,
        status="pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def run_scenario_only(
    db: Session, settings: Settings, dataset_id: uuid.UUID, question: str
) -> scenario_engine.ScenarioResult:
    """The stateless what-if calculation - never persisted (see
    app/decision/__init__.py)."""
    dataset = ingestion_service.get_dataset(db, dataset_id)
    columns = sorted(dataset.columns, key=lambda c: c.position)
    return scenario_engine.run_scenario(db, settings, dataset, columns, question)


def get_recommendation(db: Session, recommendation_id: uuid.UUID) -> Recommendation:
    record = db.get(Recommendation, recommendation_id)
    if record is None:
        raise RecommendationNotFoundError(f"Recommendation {recommendation_id} not found.")
    return record


def list_recommendations(
    db: Session, dataset_id: uuid.UUID | None = None, limit: int = 50
) -> list[Recommendation]:
    stmt = select(Recommendation).order_by(Recommendation.created_at.desc()).limit(limit)
    if dataset_id is not None:
        stmt = stmt.where(Recommendation.dataset_id == dataset_id)
    return list(db.execute(stmt).scalars())


def _decide(db: Session, recommendation_id: uuid.UUID, user: User, status: str) -> Recommendation:
    record = get_recommendation(db, recommendation_id)
    if record.status != "pending":
        raise InvalidDecisionActionError(
            f"Recommendation {recommendation_id} is already '{record.status}' - it cannot be decided again."
        )
    record.status = status
    record.decided_by = user.id
    record.decided_at = _utcnow()
    db.commit()
    db.refresh(record)
    return record


def approve_recommendation(db: Session, recommendation_id: uuid.UUID, user: User) -> Recommendation:
    return _decide(db, recommendation_id, user, "approved")


def reject_recommendation(db: Session, recommendation_id: uuid.UUID, user: User) -> Recommendation:
    return _decide(db, recommendation_id, user, "rejected")
