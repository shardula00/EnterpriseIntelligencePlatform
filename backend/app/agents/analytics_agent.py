"""Analytics agent: natural-language questions over a specific dataset.

Wraps app.analytics.service.run_query directly - the same deterministic
NL-to-SQL pipeline (parse -> build -> guard -> execute) POST /analytics/query
already uses. This agent never re-implements or bypasses any of that; it
only decides *whether* to call it, based on the current user's permission.
"""

import uuid

from sqlalchemy.orm import Session

from app.agents.base import AgentOutcome, ToolOutcome
from app.analytics.service import run_query
from app.config import Settings
from app.models.user import User
from app.rbac.service import has_permission

_ASK_PERMISSION = "analytics:query"


def ask(db: Session, settings: Settings, user: User, question: str, dataset_id: uuid.UUID | None) -> ToolOutcome:
    if not has_permission(user, _ASK_PERMISSION):
        return ToolOutcome(
            tool="ask",
            allowed=False,
            summary=f"You don't have permission ({_ASK_PERMISSION}) to ask analytics questions.",
        )
    if dataset_id is None:
        return ToolOutcome(
            tool="ask",
            allowed=True,
            summary="An analytics question needs a dataset to run against - none was specified.",
        )

    result = run_query(db, settings, dataset_id, question, user.id)
    if result.status != "answered":
        summary = result.error_message or "This question could not be answered from the dataset."
        return ToolOutcome(tool="ask", allowed=True, summary=summary, data={"status": result.status})

    return ToolOutcome(
        tool="ask",
        allowed=True,
        summary=f"Answered from '{result.dataset.name}': {result.generated_sql}",
        data={
            "status": result.status,
            "generated_sql": result.generated_sql,
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count,
        },
    )


def run(db: Session, settings: Settings, user: User, question: str, dataset_id: uuid.UUID | None) -> AgentOutcome:
    return AgentOutcome(agent="analytics", outcomes=[ask(db, settings, user, question, dataset_id)])
