"""Knowledge graph: entities and relationships derived from ingested
dataset data (Phase 9).

Plain relational tables in the same Postgres database - see
ARCHITECTURE.md §6/§7: a dedicated graph database (Neo4j or otherwise) is
deliberately not introduced; entities/relationships as rows, joined like
any other table, is the "smallest architecture that could work" this phase
committed to. `kg_` prefix (rather than bare `entities`/`relationships`)
just avoids two very generic table names colliding with future concepts.

Global/org-wide, like Dataset itself - not per-user like RAG documents
(see app/rag/__init__.py for that contrast). Built from a dataset's data,
visible to anyone who can already query that data.

No ORM relationship() between Relationship and Entity: Relationship has
two independent foreign keys into the same kg_entities table
(subject_entity_id, object_entity_id), and app/kg/graph_retrieval.py
already needs explicit joins keyed on which side it's traversing - adding
relationship() attributes here would need explicit foreign_keys= on both
sides for no real benefit over the plain joins the service layer already
writes.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Entity(Base):
    __tablename__ = "kg_entities"
    __table_args__ = (
        UniqueConstraint("dataset_id", "entity_type", "name", name="uq_kg_entity_dataset_type_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # CASCADE: an entity extracted from a dataset is meaningless once that
    # dataset is gone - same reasoning as MLRun.dataset_id/
    # AnalyticsQuery.dataset_id.
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # "Customer" | "Product" | "Category" | "Region" | "Order" - see
    # app/kg/entity_extraction.py for how each is detected/created. Not a
    # DB enum: entity types are a small, code-level constant list today,
    # but nothing here should require a migration to extend it later.
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Reserved for future per-entity metadata - unused by Phase 9's own
    # logic today (see app/kg/entity_extraction.py's docstring).
    attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)


class Relationship(Base):
    __tablename__ = "kg_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The row-level "Order" hub entity this relationship originates from -
    # see app/kg/entity_extraction.py's module docstring for why every
    # relationship is a direct, literal fact from one source row, never a
    # pre-computed aggregate/inferred edge between two leaf entities.
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "HAS_CUSTOMER" | "HAS_PRODUCT" | "HAS_CATEGORY" | "HAS_REGION".
    predicate: Mapped[str] = mapped_column(String(50), nullable=False)
    object_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
