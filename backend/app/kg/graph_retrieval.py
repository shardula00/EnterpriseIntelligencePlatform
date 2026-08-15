"""Question -> matched entities -> connected facts.

Packaged as app.rag.retrieval.RetrievedChunk - the exact same shape vector
retrieval already produces - so app/rag/llm.py's build_prompt() and
app/rag/service.py's _to_sources() need zero changes to consume either
kind of evidence. document_id/chunk_id are deterministic synthetic UUIDs
(derived from the entity, via uuid.uuid5) purely to satisfy that dataclass's
typed fields - they're never looked up as a real foreign key, and
`filename` is set to "Knowledge Graph: <dataset>" specifically so a graph
fact is visibly distinguishable from a document-sourced one in citations.

Global/org-wide: searches across every graph-built dataset's entities, not
scoped to a document or the asking user - see app/kg/__init__.py.
"""

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.kg import Entity, Relationship
from app.rag.retrieval import RetrievedChunk

# Fixed namespace for deterministic synthetic UUIDs - see module docstring.
_KG_NAMESPACE = uuid.UUID("6f2b6e0a-6b7b-4b7e-9d1a-8e6f7c9a1b2c")

# Below this length, a substring match against the question is too likely
# to be noise (e.g. an entity named "A" matching almost anything).
_MIN_ENTITY_NAME_LENGTH = 3
_MAX_SIBLINGS_PER_TYPE = 10


def _find_mentioned_entities(db: Session, question: str) -> list[Entity]:
    """Every known entity whose name is literally a substring of the
    question, case-insensitive. Fetches the full entity table and filters
    in Python rather than a reverse-LIKE SQL expression - simpler to read,
    and entity counts at this project's scale don't need the SQL-side
    version (same "acceptable at this scale, revisit if it grows"
    tradeoff this codebase makes elsewhere, e.g. app/bi/service.py)."""
    question_lower = question.lower()
    candidates = db.execute(select(Entity)).scalars().all()
    return [
        entity
        for entity in candidates
        if len(entity.name) >= _MIN_ENTITY_NAME_LENGTH and entity.name.lower() in question_lower
    ]


def _connected_entities(db: Session, entity: Entity) -> tuple[dict[str, list[Entity]], int]:
    """Entities reachable from `entity` via a shared Order-hub relationship,
    grouped by entity_type, plus how many orders connect them. Empty dict
    if `entity` has no relationships at all (an isolated entity - see
    retrieve()'s docstring on why that's a normal outcome, not an error)."""
    if entity.entity_type == "Order":
        order_ids = [entity.id]
    else:
        order_ids = list(
            db.execute(
                select(Relationship.subject_entity_id).where(
                    Relationship.object_entity_id == entity.id
                )
            ).scalars()
        )
    if not order_ids:
        return {}, 0

    rows = db.execute(
        select(Relationship, Entity)
        .join(Entity, Relationship.object_entity_id == Entity.id)
        .where(Relationship.subject_entity_id.in_(order_ids))
    ).all()

    grouped: dict[str, list[Entity]] = defaultdict(list)
    seen_ids = {entity.id}
    for _relationship, sibling in rows:
        if sibling.id in seen_ids:
            continue
        seen_ids.add(sibling.id)
        grouped[sibling.entity_type].append(sibling)
    return grouped, len(order_ids)


def _describe(entity: Entity, grouped: dict[str, list[Entity]], order_count: int) -> str:
    parts = []
    for entity_type in sorted(grouped):
        siblings = grouped[entity_type]
        names = [s.name for s in siblings[:_MAX_SIBLINGS_PER_TYPE]]
        overflow = len(siblings) - _MAX_SIBLINGS_PER_TYPE
        suffix = f" and {overflow} more" if overflow > 0 else ""
        parts.append(f"{entity_type}: {', '.join(names)}{suffix}")
    via = f"{order_count} order{'s' if order_count != 1 else ''}"
    return f'"{entity.name}" ({entity.entity_type}) is connected via {via} to: ' + "; ".join(parts) + "."


def retrieve(db: Session, question: str, max_facts: int) -> list[RetrievedChunk]:
    """Deliberately returns [] rather than raising when nothing useful is
    found - "no graph-derivable answer for this question" is a normal,
    honest outcome (see app/rag/service.py's run_query(), which falls back
    to vector-only evidence, or insufficient_evidence if that's empty too -
    hybrid mode never turns a real "I don't know" into a fabricated one)."""
    matched = _find_mentioned_entities(db, question)
    if not matched:
        return []

    dataset_names = {d.id: d.name for d in db.execute(select(Dataset)).scalars()}

    facts: list[RetrievedChunk] = []
    for entity in matched:
        grouped, order_count = _connected_entities(db, entity)
        if not grouped:
            continue  # matched a real entity, but it has no useful connections

        facts.append(
            RetrievedChunk(
                chunk_id=uuid.uuid5(_KG_NAMESPACE, f"chunk:{entity.id}"),
                document_id=uuid.uuid5(_KG_NAMESPACE, f"dataset:{entity.dataset_id}"),
                filename=f"Knowledge Graph: {dataset_names.get(entity.dataset_id, 'dataset')}",
                chunk_index=0,
                page_number=None,
                section_title=entity.entity_type,
                content=_describe(entity, grouped, order_count),
                score=1.0,  # an exact name match against real data, not a similarity score
                rank=0,  # re-numbered by app/rag/service.py after merging with vector chunks
            )
        )
        if len(facts) >= max_facts:
            break

    return facts
