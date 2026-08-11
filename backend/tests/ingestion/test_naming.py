import uuid

from app.ingestion.naming import (
    MAX_IDENTIFIER_LENGTH,
    dedupe_identifiers,
    make_table_name,
    sanitize_identifier,
)


def test_simple_name_is_lowercased():
    assert sanitize_identifier("CustomerName") == "customername"


def test_spaces_and_punctuation_become_underscores():
    assert sanitize_identifier("Revenue (EUR)") == "revenue_eur"


def test_accented_characters_are_stripped():
    assert sanitize_identifier("Preço") == "preco"


def test_leading_digit_gets_prefixed():
    assert sanitize_identifier("2024_total") == "col_2024_total"


def test_empty_or_symbol_only_input_falls_back():
    assert sanitize_identifier("") == "col"
    assert sanitize_identifier("!!!") == "col"
    assert sanitize_identifier(None) == "col"  # type: ignore[arg-type]


def test_sql_injection_attempt_is_neutralized():
    malicious = "'); DROP TABLE users; --"
    result = sanitize_identifier(malicious)

    assert result.isascii()
    assert all(c.isalnum() or c == "_" for c in result)
    assert ";" not in result
    assert "'" not in result
    assert "--" not in result or "-" not in result  # no literal hyphen survives either


def test_long_name_is_truncated_within_postgres_limit():
    long_name = "x" * 200
    result = sanitize_identifier(long_name)
    assert len(result) <= MAX_IDENTIFIER_LENGTH


def test_dedupe_identifiers_keeps_first_and_suffixes_rest():
    result = dedupe_identifiers(["total", "total", "total", "region"])
    assert result == ["total", "total_2", "total_3", "region"]


def test_dedupe_identifiers_respects_length_limit_when_suffixing():
    long_base = "a" * 63
    result = dedupe_identifiers([long_base, long_base])
    assert result[0] == long_base
    assert len(result[1]) <= MAX_IDENTIFIER_LENGTH
    assert result[1].endswith("_2")
    assert result[0] != result[1]


def test_make_table_name_is_deterministic_and_safe():
    dataset_id = uuid.uuid4()
    name = make_table_name(dataset_id)
    assert name == f"ds_{dataset_id.hex}"
    assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in name)
