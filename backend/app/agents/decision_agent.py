"""Decision agent: composes ML/Risk output (from earlier in the same
orchestration run - see orchestrator.py's `prior_outcomes`) into a
persisted, human-approvable recommendation, or runs a stateless what-if
scenario when no ML/Risk context is available in this run. Wraps
app.decision.service directly - the same functions POST /decisions and
POST /decisions/scenario already call.

Deliberately not modified: ml_agent.py/risk_agent.py/analytics_agent.py -
this agent only ever reads their *already-produced* ToolOutcome objects
via `prior_outcomes`, never their internals.
"""

import uuid

from sqlalchemy.orm import Session

from app.agents.base import AgentOutcome, ToolOutcome
from app.config import Settings
from app.decision.service import propose_recommendation, run_scenario_only
from app.models.user import User
from app.rbac.service import has_permission

_DECIDE_PERMISSION = "decision:propose"


def decide(
    db: Session,
    settings: Settings,
    user: User,
    question: str,
    dataset_id: uuid.UUID | None,
    prior_outcomes: list[AgentOutcome],
) -> ToolOutcome:
    if not has_permission(user, _DECIDE_PERMISSION):
        return ToolOutcome(
            tool="decide",
            allowed=False,
            summary=f"You don't have permission ({_DECIDE_PERMISSION}) to generate recommendations.",
        )
    if dataset_id is None:
        return ToolOutcome(
            tool="decide",
            allowed=True,
            summary="A decision needs a dataset to run against - none was specified.",
        )

    has_ml_or_risk_context = any(ao.agent in ("ml", "risk") for ao in prior_outcomes)
    if has_ml_or_risk_context:
        record = propose_recommendation(db, settings, user, dataset_id, question, prior_outcomes)
        return ToolOutcome(
            tool="propose",
            allowed=True,
            summary=record.recommendation,
            data={
                "id": str(record.id),
                "status": record.status,
                "confidence": record.confidence,
                "alternatives": record.alternatives,
                "risks": record.risks,
                "assumptions": record.assumptions,
                "expected_impact": record.expected_impact,
            },
        )

    result = run_scenario_only(db, settings, dataset_id, question)
    summary = result.note if result.computed else (result.reason or "This scenario could not be computed.")
    return ToolOutcome(
        tool="scenario",
        allowed=True,
        summary=summary,
        data={
            "computed": result.computed,
            "affected_metric": result.affected_metric,
            "perturbed_metric": result.perturbed_metric,
            "delta_percent": result.delta_percent,
            "baseline_affected_value": result.baseline_affected_value,
            "new_affected_value": result.new_affected_value,
            "affected_value_change": result.affected_value_change,
            "relationship": result.relationship,
            "reason": result.reason,
        },
    )


def run(
    db: Session,
    settings: Settings,
    user: User,
    question: str,
    dataset_id: uuid.UUID | None,
    prior_outcomes: list[AgentOutcome],
) -> AgentOutcome:
    return AgentOutcome(agent="decision", outcomes=[decide(db, settings, user, question, dataset_id, prior_outcomes)])
