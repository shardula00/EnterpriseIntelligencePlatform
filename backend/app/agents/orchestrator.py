"""The full question -> route -> invoke agent(s) -> compose pipeline - the
only module app/api/agents.py calls.

A small mutable `context` dict is threaded through every agent invoked in
one plan, so a later agent can use an earlier one's output (today, just
ml_agent writing context["ml_run_id"] for risk_agent to read) without the
agents importing each other or the orchestrator needing to know each
agent's internal result shape.

Phase 11: the growing `agent_outcomes` list (every agent's result *so
far* in this same run) is also passed to decision_agent, since Decision
needs to read what ML/Risk already produced (not just a single id) without
ml_agent.py/risk_agent.py needing to change to write anything new to
`context` themselves - see app/agents/decision_agent.py.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents import analytics_agent, data_agent, decision_agent, ml_agent, research_agent, risk_agent
from app.agents.base import AgentOutcome
from app.agents.router import route
from app.config import Settings
from app.models.user import User

UNSUPPORTED_MESSAGE = (
    "I couldn't determine which capability this request needs. Try mentioning "
    "forecasting/training, analytics totals/breakdowns, dataset details, risk flags, "
    "or a document/research question explicitly."
)


@dataclass
class OrchestrationResult:
    question: str
    status: str  # "answered" | "unsupported"
    agents_invoked: list[str] = field(default_factory=list)
    agent_outcomes: list[AgentOutcome] = field(default_factory=list)
    summary: str = ""


def _run_agent(
    name: str,
    db: Session,
    settings: Settings,
    user: User,
    question: str,
    dataset_id: uuid.UUID | None,
    context: dict,
    prior_outcomes: list[AgentOutcome],
) -> AgentOutcome:
    if name == "data":
        return data_agent.run(db, user, dataset_id)
    if name == "analytics":
        return analytics_agent.run(db, settings, user, question, dataset_id)
    if name == "ml":
        return ml_agent.run(db, settings, user, question, dataset_id, context)
    if name == "research":
        return research_agent.run(db, settings, user, question)
    if name == "risk":
        return risk_agent.run(db, user, dataset_id, context)
    if name == "decision":
        return decision_agent.run(db, settings, user, question, dataset_id, prior_outcomes)
    raise ValueError(f"Unknown agent '{name}'")  # pragma: no cover - route() only emits known names


def _compose_summary(agent_outcomes: list[AgentOutcome]) -> str:
    parts = [
        outcome.summary
        for agent_outcome in agent_outcomes
        for outcome in agent_outcome.outcomes
        if outcome.summary
    ]
    return " ".join(parts)


def run(
    db: Session,
    settings: Settings,
    user: User,
    question: str,
    dataset_id: uuid.UUID | None,
) -> OrchestrationResult:
    plan = route(question)
    if not plan:
        return OrchestrationResult(
            question=question, status="unsupported", agents_invoked=[], summary=UNSUPPORTED_MESSAGE
        )

    context: dict = {}
    agent_outcomes: list[AgentOutcome] = []
    for name in plan:
        outcome = _run_agent(name, db, settings, user, question, dataset_id, context, agent_outcomes)
        agent_outcomes.append(outcome)

    return OrchestrationResult(
        question=question,
        status="answered",
        agents_invoked=plan,
        agent_outcomes=agent_outcomes,
        summary=_compose_summary(agent_outcomes),
    )
