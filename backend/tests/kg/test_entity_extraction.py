"""Tests for app/kg/entity_extraction.py against a real Postgres
(db_session) - column-matching is pure Python, build_graph() reads the
dataset's real physical table."""

import pytest
from sqlalchemy import select

from app.config import Settings
from app.ingestion import service as ingestion_service
from app.kg.entity_extraction import BuildResult, build_graph, detect_entity_columns
from app.models.dataset import DatasetColumn
from app.models.kg import Entity, Relationship
from tests.conftest import FIXTURES_DIR

ORDERS_SAMPLE = (FIXTURES_DIR / "orders_sample.csv").read_bytes()


def _col(position: int, name: str, detected_type: str) -> DatasetColumn:
    return DatasetColumn(
        position=position,
        original_name=name.title(),
        column_name=name,
        detected_type=detected_type,
        nullable=True,
        null_count=0,
        distinct_count=5,
    )


# ---------------------------------------------------------------------------
# detect_entity_columns - pure Python, no database
# ---------------------------------------------------------------------------


def test_detect_entity_columns_matches_synonyms_not_just_exact_names():
    columns = [
        _col(0, "customer_name", "text"),  # "customer" synonym, not the exact word "Customer"
        _col(1, "product", "text"),
        _col(2, "category", "text"),
        _col(3, "region", "text"),
    ]
    detected = detect_entity_columns(columns)
    assert detected["Customer"].column_name == "customer_name"
    assert detected["Product"].column_name == "product"
    assert detected["Category"].column_name == "category"
    assert detected["Region"].column_name == "region"


def test_detect_entity_columns_ignores_numeric_and_datetime_columns():
    columns = [
        _col(0, "quantity", "integer"),
        _col(1, "unit_price", "float"),
        _col(2, "order_date", "datetime"),
    ]
    assert detect_entity_columns(columns) == {}


def test_detect_entity_columns_never_assigns_one_column_to_two_types():
    # A single ambiguous column can't satisfy two entity types at once.
    columns = [_col(0, "customer_region", "text")]
    detected = detect_entity_columns(columns)
    assert len(detected) == 1
    assigned_columns = {c.column_name for c in detected.values()}
    assert len(assigned_columns) == len(detected)


def test_detect_entity_columns_returns_empty_when_nothing_matches():
    columns = [_col(0, "notes", "text"), _col(1, "is_archived", "boolean")]
    assert detect_entity_columns(columns) == {}


# ---------------------------------------------------------------------------
# build_graph - integration, real Postgres
# ---------------------------------------------------------------------------


@pytest.fixture
def dataset(db_session):
    return ingestion_service.ingest_upload(db_session, Settings(), "orders_sample.csv", ORDERS_SAMPLE)


def test_build_graph_creates_order_hub_and_leaf_entities(db_session, dataset):
    columns = sorted(dataset.columns, key=lambda c: c.position)
    result = build_graph(db_session, dataset, columns)

    assert result.entity_types == ["Category", "Customer", "Order", "Product", "Region"]
    # 20 distinct orders + <=20 distinct values per Customer/Product/Category/Region.
    assert result.entity_count > 20
    assert result.relationship_count == 20 * 4  # 4 recognized columns x 20 rows

    orders = db_session.execute(
        select(Entity).where(Entity.dataset_id == dataset.id, Entity.entity_type == "Order")
    ).scalars().all()
    assert len(orders) == 20
    # order_id is the id-like column, so Order entities are named "1".."20", not "Row 1".
    assert {o.name for o in orders} == {str(i) for i in range(1, 21)}

    regions = db_session.execute(
        select(Entity).where(Entity.dataset_id == dataset.id, Entity.entity_type == "Region")
    ).scalars().all()
    assert {r.name for r in regions} == {"North", "South", "East", "West"}


def test_build_graph_relationships_are_literal_row_facts(db_session, dataset):
    columns = sorted(dataset.columns, key=lambda c: c.position)
    build_graph(db_session, dataset, columns)

    alice = db_session.execute(
        select(Entity).where(Entity.dataset_id == dataset.id, Entity.name == "Alice Johnson")
    ).scalar_one()
    # Alice Johnson (row 1) placed exactly one order in orders_sample.csv.
    edges = db_session.execute(
        select(Relationship).where(Relationship.object_entity_id == alice.id)
    ).scalars().all()
    assert len(edges) == 1
    assert edges[0].predicate == "HAS_CUSTOMER"


def test_build_graph_is_idempotent_on_rebuild(db_session, dataset):
    columns = sorted(dataset.columns, key=lambda c: c.position)
    first = build_graph(db_session, dataset, columns)
    second = build_graph(db_session, dataset, columns)

    assert second.entity_count == first.entity_count
    assert second.relationship_count == first.relationship_count

    total_entities = db_session.execute(
        select(Entity).where(Entity.dataset_id == dataset.id)
    ).scalars().all()
    assert len(total_entities) == first.entity_count  # not doubled


def test_build_graph_returns_nothing_for_a_dataset_with_no_entity_columns(db_session, dataset):
    numeric_and_datetime_columns = [
        c for c in dataset.columns if c.detected_type not in ("text", "boolean")
    ]
    result = build_graph(db_session, dataset, numeric_and_datetime_columns)

    assert result == BuildResult(entity_count=0, relationship_count=0, entity_types=[])
    assert db_session.execute(
        select(Entity).where(Entity.dataset_id == dataset.id)
    ).first() is None
