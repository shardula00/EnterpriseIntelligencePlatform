"""Multi-agent orchestration API (Phase 10): run a natural-language
request against the deterministic agent orchestrator, and list the fixed
agent catalog.

Thin HTTP layer only - all logic lives in app/agents/orchestrator.py. No
standalone per-agent endpoints: every agent is only ever reached through
POST /agents/run (see app/agents/__init__.py).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents import orchestrator
from app.agents.schemas import (
    AgentCatalogEntryOut,
    AgentOutcomeOut,
    AgentRunRequest,
    AgentRunResponseOut,
    ToolOutcomeOut,
)
from app.audit.service import AuditAction, record_event
from app.config import Settings, get_settings
from app.db import get_db
from app.ingestion.errors import DatasetNotFoundError
from app.models.user import User
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/agents", tags=["agents"])

# A fixed, code-level catalog - not persisted, not dynamically discovered.
# Kept in sync with app/agents/{data,analytics,ml,research,risk}_agent.py
# by hand, the same way this project documents any other fixed constant
# list (e.g. app/rbac/seed.py's PERMISSION_CATALOG).
CATALOG: list[AgentCatalogEntryOut] = [
    AgentCatalogEntryOut(
        name="data",
        description="Lists and describes uploaded datasets (read-only).",
        tools=["list_datasets", "describe_dataset"],
    ),
    AgentCatalogEntryOut(
        name="analytics",
        description="Answers natural-language analytical questions against a specific dataset.",
        tools=["ask"],
    ),
    AgentCatalogEntryOut(
        name="ml",
        description="Checks forecasting suitability and trains a forecast for a dataset.",
        tools=["check_suitability", "forecast"],
    ),
    AgentCatalogEntryOut(
        name="research",
        description="Answers grounded questions from uploaded documents and, in hybrid mode, the knowledge graph.",
        tools=["answer"],
    ),
    AgentCatalogEntryOut(
        name="risk",
        description="Flags notable risk signals from a forecast's trend/uncertainty and existing monitoring events.",
        tools=["assess_risk"],
    ),
]


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[AgentCatalogEntryOut])
def list_agents(
    current_user: User = Depends(require_permission("agents:run")),
) -> list[AgentCatalogEntryOut]:
    return CATALOG


@router.post("/run", response_model=AgentRunResponseOut)
def run_agents(
    request: Request,
    body: AgentRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("agents:run")),
) -> AgentRunResponseOut:
    try:
        result = orchestrator.run(db, settings, current_user, body.question, body.dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Deliberately just which agents ran and the outcome status - not the
    # full answer text/data, which can reflect private dataset/document
    # content (same reasoning as every other Phase 7-9 audit event).
    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.AGENT_RUN_PERFORMED,
        resource_type="agent_run",
        resource_id=str(body.dataset_id) if body.dataset_id else None,
        metadata={"agents_invoked": result.agents_invoked, "status": result.status},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    return AgentRunResponseOut(
        question=result.question,
        status=result.status,
        agents_invoked=result.agents_invoked,
        agent_outcomes=[
            AgentOutcomeOut(
                agent=agent_outcome.agent,
                outcomes=[
                    ToolOutcomeOut(
                        tool=o.tool, allowed=o.allowed, summary=o.summary, data=o.data
                    )
                    for o in agent_outcome.outcomes
                ],
            )
            for agent_outcome in result.agent_outcomes
        ],
        summary=result.summary,
    )
