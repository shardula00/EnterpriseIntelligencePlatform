"""Dataset columns/rows -> Entity/Relationship rows - the "population"
step behind POST /datasets/{dataset_id}/graph/build.

Entity types are recognized generically, by matching a dataset's real
text/boolean column names against a small synonym table - the same
"match question/column tokens against a small synonym list, never a
hardcoded business column name" approach app/analytics/nl_parser.py
already established (independently re-implemented here rather than
imported, since each module's matching is tiny and self-contained - the
same "each module owns its own small heuristic" pattern app/bi/service.py
also follows). Numeric columns never become entity types - they stay
analytics' territory (Phase 8), not graph nodes.

"Order" is not synonym-detected - it's the implicit per-row hub, created
for every row that has at least one recognized entity value, so that
distinct leaf entities (a Customer, a Product) end up connected to each
other through the row that actually mentioned them together.

Relationships are *only* direct, literal facts already present in one
source row: `(Order, "HAS_<TYPE>", EntityValue)`. This module deliberately
never pre-computes/materializes an inferred edge between two leaf entities
(e.g. Product -> Category derived from "every row where Product=X has
Category=Y") - that would be a real statistical inference that can be
wrong on messy data. Multi-hop facts are answered by traversing through
the Order hub at query time instead (see app/kg/graph_retrieval.py).

Idempotent: build_graph() always deletes a dataset's previous
entities/relationships before recreating them, so rebuilding is just
"run it again," never a diff.
"""

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ingestion.table_builder import build_dataset_table
from app.models.dataset import Dataset, DatasetColumn
from app.models.kg import Entity, Relationship

ORDER_ENTITY_TYPE = "Order"

# Small, generic business-terminology synonyms, same reasoning and same
# shape as app/analytics/nl_parser.py's _SYNONYMS - common English business
# words, not a lookup table of any specific dataset's own column names.
_ENTITY_TYPE_SYNONYMS: dict[str, list[str]] = {
    "Customer": ["customer", "client", "account"],
    "Product": ["product", "item"],
    "Category": ["category", "type", "segment"],
    "Region": ["region", "area", "territory", "location"],
}

_ENTITY_COLUMN_TYPES = ("text", "boolean")


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def detect_entity_columns(columns: list[DatasetColumn]) -> dict[str, DatasetColumn]:
    """Map entity_type -> the single best-matching text/boolean column, if
    any. Each column is assigned to at most one entity type (the first,
    highest-scoring match, in `_ENTITY_TYPE_SYNONYMS`'s fixed iteration
    order) so two entity types can never collapse onto the same column."""
    candidates = [c for c in columns if c.detected_type in _ENTITY_COLUMN_TYPES]
    used_columns: set[str] = set()
    detected: dict[str, DatasetColumn] = {}

    for entity_type, synonyms in _ENTITY_TYPE_SYNONYMS.items():
        best: DatasetColumn | None = None
        best_score = 0
        for column in candidates:
            if column.column_name in used_columns:
                continue
            tokens = _tokenize(column.original_name) | _tokenize(column.column_name)
            score = len(tokens & set(synonyms))
            if score > best_score:
                best, best_score = column, score
        if best is not None:
            detected[entity_type] = best
            used_columns.add(best.column_name)

    return detected


def _detect_id_column(columns: list[DatasetColumn]) -> DatasetColumn | None:
    """A column whose name suggests it's the row's own natural identifier
    (e.g. "order_id", "id") - used only to give the per-row Order entity a
    readable name. Purely cosmetic: if this picks the wrong column, Order
    entities just get a less ideal display name, never a correctness bug -
    see build_graph()'s fallback to "Row {index}" when none is found."""
    for column in columns:
        tokens = _tokenize(column.original_name) | _tokenize(column.column_name)
        if "id" in tokens:
            return column
    return None


@dataclass
class BuildResult:
    entity_count: int
    relationship_count: int
    entity_types: list[str] = field(default_factory=list)


def build_graph(db: Session, dataset: Dataset, columns: list[DatasetColumn]) -> BuildResult:
    """Rebuild `dataset`'s knowledge graph from its physical table.
    Returns (0, 0, []) - not an error - if the dataset has no recognizable
    entity columns at all; a dataset of pure numeric/datetime columns
    simply has nothing for this phase to build a graph from."""
    # Idempotent rebuild: clear this dataset's previous graph first.
    db.execute(delete(Relationship).where(Relationship.dataset_id == dataset.id))
    db.execute(delete(Entity).where(Entity.dataset_id == dataset.id))

    entity_columns = detect_entity_columns(columns)
    if not entity_columns:
        db.commit()
        return BuildResult(entity_count=0, relationship_count=0, entity_types=[])

    id_column = _detect_id_column(columns)
    column_map = {c.column_name: c.detected_type for c in columns}
    table = build_dataset_table(dataset.storage_table_name, column_map)

    select_columns = [table.c[c.column_name] for c in entity_columns.values()]
    if id_column is not None:
        select_columns.append(table.c[id_column.column_name])
    rows = db.connection().execute(select(*select_columns)).all()

    entity_cache: dict[tuple[str, str], Entity] = {}

    def get_or_create_entity(entity_type: str, name: str) -> Entity:
        key = (entity_type, name)
        cached = entity_cache.get(key)
        if cached is not None:
            return cached
        # id generated explicitly (not left to the column's Python-side
        # default) so it's usable as a Relationship FK immediately, before
        # any flush - same pattern app/rag/service.py's upload_document()
        # uses for the same reason.
        entity = Entity(id=uuid.uuid4(), dataset_id=dataset.id, entity_type=entity_type, name=name)
        db.add(entity)
        entity_cache[key] = entity
        return entity

    relationship_count = 0
    for row_index, row in enumerate(rows, start=1):
        row_map = row._mapping
        present = {
            entity_type: str(row_map[column.column_name])
            for entity_type, column in entity_columns.items()
            if row_map[column.column_name] is not None and str(row_map[column.column_name]).strip()
        }
        if not present:
            continue  # nothing recognizable in this row - no Order to anchor it to

        if id_column is not None and row_map.get(id_column.column_name) is not None:
            order_name = str(row_map[id_column.column_name])
        else:
            order_name = f"Row {row_index}"
        order_entity = get_or_create_entity(ORDER_ENTITY_TYPE, order_name)

        for entity_type, value in present.items():
            value_entity = get_or_create_entity(entity_type, value)
            db.add(
                Relationship(
                    id=uuid.uuid4(),
                    dataset_id=dataset.id,
                    subject_entity_id=order_entity.id,
                    predicate=f"HAS_{entity_type.upper()}",
                    object_entity_id=value_entity.id,
                )
            )
            relationship_count += 1

    db.commit()
    return BuildResult(
        entity_count=len(entity_cache),
        relationship_count=relationship_count,
        entity_types=sorted({entity_type for entity_type, _name in entity_cache}),
    )
