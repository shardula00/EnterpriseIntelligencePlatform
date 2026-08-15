"""Integration tests for app/analytics/service.py against a real Postgres,
never the HTTP layer (that's tests/test_analytics_api.py) - unit-level
coverage for the underlying pieces (parsing, query building, SQL
validation) lives in this same tests/analytics/ package."""

import uuid

import pytest
from sqlalchemy import text

from app.analytics import service
from app.config import Settings
from app.ingestion import service as ingestion_service
from app.ingestion.errors import DatasetNotFoundError
from tests.conftest import FIXTURES_DIR, _create_user_with_role


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def user(db_session):
    return _create_user_with_role(db_session, "ANALYST")


@pytest.fixture
def dataset(db_session):
    content = (FIXTURES_DIR / "orders_sample.csv").read_bytes()
    return ingestion_service.ingest_upload(db_session, Settings(), "orders_sample.csv", content)


def test_total_question_returns_a_single_row_with_the_real_sum(db_session, settings, dataset, user):
    query = service.run_query(db_session, settings, dataset.id, "What is the total quantity?", user.id)

    assert query.status == "answered"
    assert query.intent == "total"
    assert query.generated_sql is not None
    assert query.generated_sql.upper().startswith("SELECT")
    assert query.row_count == 1
    assert query.rows[0]["quantity"] == 65


def test_count_question_returns_the_real_row_count(db_session, settings, dataset, user):
    # Regression for the "total" + "count" missing-FROM bug: bare
    # func.count() has no table affiliation, so this must render with an
    # explicit FROM clause referencing the dataset's own table - the same
    # thing sql_guard.py's "does the SQL reference the expected table"
    # check independently re-verifies. orders_sample.csv has exactly 20
    # data rows (no checked-in phase8_sales.csv fixture exists to assert
    # 28 against - this is the equivalent real-execution check).
    query = service.run_query(
        db_session, settings, dataset.id, "How many rows are in this dataset?", user.id
    )

    assert query.status == "answered"
    assert query.intent == "total"
    assert query.generated_sql is not None
    assert "FROM" in query.generated_sql.upper()
    assert dataset.storage_table_name in query.generated_sql
    assert query.row_count == 1
    assert query.rows[0]["count"] == 20


def test_how_many_orders_question_also_returns_the_real_row_count(
    db_session, settings, dataset, user
):
    query = service.run_query(db_session, settings, dataset.id, "How many orders are there?", user.id)

    assert query.status == "answered"
    assert query.rows[0]["count"] == 20


def test_breakdown_question_returns_one_row_per_category(db_session, settings, dataset, user):
    query = service.run_query(
        db_session, settings, dataset.id, "Show total quantity by region.", user.id
    )

    assert query.status == "answered"
    assert query.intent == "breakdown"
    assert query.row_count == 4  # North/South/East/West
    assert set(query.columns) == {"region", "quantity"}


def test_top_n_question_returns_the_single_top_ranked_row(db_session, settings, dataset, user):
    query = service.run_query(
        db_session, settings, dataset.id, "Which region has the highest quantity?", user.id
    )

    assert query.status == "answered"
    assert query.intent == "top_n"
    assert query.row_count == 1


def test_unsupported_question_is_handled_gracefully_not_raised(db_session, settings, dataset, user):
    query = service.run_query(
        db_session, settings, dataset.id, "What is the weather like today?", user.id
    )

    assert query.status == "unsupported"
    assert query.generated_sql is None
    assert query.row_count == 0
    assert query.error_message


def test_whitespace_only_question_is_unsupported_not_a_crash(db_session, settings, dataset, user):
    query = service.run_query(db_session, settings, dataset.id, "   ", user.id)
    assert query.status == "unsupported"


def test_unknown_dataset_id_raises_dataset_not_found(db_session, settings, user):
    with pytest.raises(DatasetNotFoundError):
        service.run_query(db_session, settings, uuid.uuid4(), "total quantity", user.id)


def test_empty_underlying_table_produces_zero_rows_not_an_error(db_session, settings, dataset, user):
    # Simulates "the dataset genuinely has no matching data" without
    # fighting ingestion's own EmptyFileError (a 0-row upload is rejected
    # at ingestion time, by design) - delete the physical table's rows
    # directly, the same table the query would run against.
    db_session.execute(text(f"DELETE FROM ingested.{dataset.storage_table_name}"))
    db_session.commit()

    query = service.run_query(
        db_session, settings, dataset.id, "Show total quantity by region.", user.id
    )

    assert query.status == "answered"
    assert query.row_count == 0
    assert query.rows == []


def test_query_is_persisted_and_retrievable_via_get_and_list(db_session, settings, dataset, user):
    created = service.run_query(db_session, settings, dataset.id, "total quantity", user.id)

    fetched = service.get_query(db_session, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.dataset.name == dataset.name

    history = service.list_queries(db_session, dataset_id=dataset.id)
    assert any(q.id == created.id for q in history)


def test_get_query_returns_none_for_an_unknown_id(db_session):
    assert service.get_query(db_session, uuid.uuid4()) is None
