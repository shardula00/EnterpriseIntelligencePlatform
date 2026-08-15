"""Pydantic response model for the knowledge graph API (app/api/kg.py)."""

from uuid import UUID

from pydantic import BaseModel


class GraphBuildResultOut(BaseModel):
    dataset_id: UUID
    entity_count: int
    relationship_count: int
    entity_types: list[str]
