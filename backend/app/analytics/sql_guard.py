"""Defense-in-depth textual validation of the rendered SQL text before it is
returned/persisted - a second, independent check on top of the structural
guarantee app/analytics/query_builder.py already provides (it can only ever
build a single `select(...)` via SQLAlchemy Core, never a hand-assembled
string). This module should never actually reject anything the query
builder produces; it exists so that guarantee isn't the *only* thing
standing between a question and the database, and so "the generated SQL is
validated" is a real, independently testable step, not just a comment.
"""

import re

from app.analytics.errors import UnsafeSqlError

_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "MERGE", "REPLACE", "CALL",
    "COPY", "VACUUM", "ATTACH", "DETACH", "INTO",
)


def validate_select_only(sql_text: str, allowed_table: str) -> None:
    """Raises UnsafeSqlError unless `sql_text` is a single, read-only
    SELECT statement referencing only `allowed_table` (the asked-about
    dataset's own physical table)."""
    stripped = sql_text.strip()
    if not stripped:
        raise UnsafeSqlError("Generated SQL is empty.")

    upper = stripped.upper()
    if not upper.startswith("SELECT"):
        raise UnsafeSqlError("Only SELECT statements are permitted.")

    if "--" in stripped or "/*" in stripped:
        raise UnsafeSqlError("SQL comments are not permitted.")

    # A single statement only: a lone trailing semicolon is fine, but
    # anything after/before it is a second statement.
    body = stripped[:-1] if stripped.endswith(";") else stripped
    if ";" in body:
        raise UnsafeSqlError("Multiple SQL statements are not permitted.")

    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            raise UnsafeSqlError(f"Generated SQL contains a forbidden keyword: {keyword}.")

    if allowed_table.lower() not in stripped.lower():
        raise UnsafeSqlError("Generated SQL does not reference the expected dataset table.")
