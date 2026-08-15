"""Unit tests for app/analytics/sql_guard.py - the defense-in-depth
textual re-check on top of query_builder.py's structural safety."""

import pytest

from app.analytics.errors import UnsafeSqlError
from app.analytics.sql_guard import validate_select_only


def test_a_real_generated_select_passes():
    sql = "SELECT sum(ingested.ds_x.revenue) AS revenue \nFROM ingested.ds_x"
    validate_select_only(sql, allowed_table="ds_x")  # must not raise


def test_rejects_a_statement_that_does_not_start_with_select():
    with pytest.raises(UnsafeSqlError):
        validate_select_only("DROP TABLE ingested.ds_x", allowed_table="ds_x")


def test_rejects_delete():
    with pytest.raises(UnsafeSqlError):
        validate_select_only("DELETE FROM ingested.ds_x", allowed_table="ds_x")


def test_rejects_insert():
    with pytest.raises(UnsafeSqlError):
        validate_select_only(
            "SELECT 1; INSERT INTO ingested.ds_x VALUES (1)", allowed_table="ds_x"
        )


def test_rejects_update():
    with pytest.raises(UnsafeSqlError):
        validate_select_only("UPDATE ingested.ds_x SET revenue = 0", allowed_table="ds_x")


def test_rejects_a_second_statement_appended_after_a_semicolon():
    with pytest.raises(UnsafeSqlError):
        validate_select_only(
            "SELECT * FROM ingested.ds_x; DROP TABLE ingested.ds_x", allowed_table="ds_x"
        )


def test_a_single_trailing_semicolon_is_still_allowed():
    validate_select_only("SELECT * FROM ingested.ds_x;", allowed_table="ds_x")  # must not raise


def test_rejects_sql_comments():
    with pytest.raises(UnsafeSqlError):
        validate_select_only(
            "SELECT * FROM ingested.ds_x -- drop everything later", allowed_table="ds_x"
        )


def test_rejects_a_query_that_does_not_reference_the_expected_table():
    with pytest.raises(UnsafeSqlError):
        validate_select_only("SELECT * FROM ingested.some_other_table", allowed_table="ds_x")


def test_rejects_empty_sql():
    with pytest.raises(UnsafeSqlError):
        validate_select_only("   ", allowed_table="ds_x")


def test_does_not_false_positive_on_column_names_containing_keyword_substrings():
    # "created_at" contains no forbidden keyword as a whole word; this must
    # not falsely trip the DROP/CREATE/etc. keyword check.
    sql = "SELECT ingested.ds_x.created_at FROM ingested.ds_x"
    validate_select_only(sql, allowed_table="ds_x")  # must not raise
