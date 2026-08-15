"""Research agent: grounded question-answering over documents and,
whenever Settings.retrieval_mode == "hybrid" (Phase 9), the knowledge
graph too - both for free, since app.rag.service.run_query() already
handles that toggle. This agent adds no retrieval logic of its own; it
only decides whether to call it.
"""

from sqlalchemy.orm import Session

from app.agents.base import AgentOutcome, ToolOutcome
from app.config import Settings
from app.models.user import User
from app.rag.embeddings import get_embedding_provider
from app.rag.llm import get_llm_provider
from app.rag.service import run_query
from app.rbac.service import has_permission

_ANSWER_PERMISSION = "rag:query"


def answer(db: Session, settings: Settings, user: User, question: str) -> ToolOutcome:
    if not has_permission(user, _ANSWER_PERMISSION):
        return ToolOutcome(
            tool="answer",
            allowed=False,
            summary=f"You don't have permission ({_ANSWER_PERMISSION}) to query the research assistant.",
        )

    embedding_provider = get_embedding_provider(settings)
    llm_provider = get_llm_provider(settings)
    result = run_query(db, settings, embedding_provider, llm_provider, user, question)

    return ToolOutcome(
        tool="answer",
        allowed=True,
        summary=result.answer,
        data={
            "status": result.status,
            "sources": result.sources,
        },
    )


def run(db: Session, settings: Settings, user: User, question: str) -> AgentOutcome:
    return AgentOutcome(agent="research", outcomes=[answer(db, settings, user, question)])
