"""Pydantic request/response models for the agents API (app/api/agents.py)."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AgentRunStatus = Literal["answered", "unsupported"]


class AgentRunRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    dataset_id: UUID | None = None


class ToolOutcomeOut(BaseModel):
    tool: str
    allowed: bool
    summary: str
    data: dict[str, Any] | None = None


class AgentOutcomeOut(BaseModel):
    agent: str
    outcomes: list[ToolOutcomeOut]


class AgentRunResponseOut(BaseModel):
    question: str
    status: AgentRunStatus
    agents_invoked: list[str]
    agent_outcomes: list[AgentOutcomeOut]
    summary: str


class AgentCatalogEntryOut(BaseModel):
    name: str
    description: str
    tools: list[str]
