"""Turns arbitrary, untrusted text (file headers) into safe Postgres identifiers.

This is the load-bearing safety mechanism for dynamic table creation: every
column/table name that reaches SQLAlchemy's DDL has already been forced
through `_ALLOWED_CHARS` below, so no header - however adversarial - can
smuggle a quote, semicolon, or space into a CREATE TABLE statement. Combined
with building tables via SQLAlchemy `Table`/`Column` objects (never raw SQL
string concatenation) in table_builder.py, this makes dynamic per-dataset
tables safe from SQL injection by construction, not by trust in the input.
"""

import re
import unicodedata
import uuid

# Postgres identifiers are limited to 63 bytes (NAMEDATALEN=64, minus the
# null terminator). We stay under that for both table and column names.
MAX_IDENTIFIER_LENGTH = 63

_DISALLOWED_CHARS = re.compile(r"[^a-z0-9_]+")
_MULTI_UNDERSCORE = re.compile(r"_+")


def sanitize_identifier(raw: str, *, fallback_prefix: str = "col") -> str:
    """Map arbitrary text to a safe, valid Postgres identifier.

    Lowercases, strips accents, replaces every character outside
    `[a-z0-9_]` with `_`, collapses repeated underscores, and ensures the
    result doesn't start with a digit or come out empty. Never raises -
    any input, including SQL metacharacters, produces *some* safe
    identifier rather than an exception, so a bad header degrades a
    column's name, not the whole upload.
    """
    if raw is None:
        raw = ""

    # Strip accents (e.g. "Revenue (EUR)" or "Preço" -> ascii-safe first).
    normalized = unicodedata.normalize("NFKD", str(raw))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")

    lowered = ascii_only.lower()
    replaced = _DISALLOWED_CHARS.sub("_", lowered)
    collapsed = _MULTI_UNDERSCORE.sub("_", replaced).strip("_")

    if not collapsed:
        collapsed = fallback_prefix
    elif collapsed[0].isdigit():
        collapsed = f"{fallback_prefix}_{collapsed}"

    return collapsed[:MAX_IDENTIFIER_LENGTH].rstrip("_") or fallback_prefix


def dedupe_identifiers(names: list[str]) -> list[str]:
    """Ensure every name in `names` is unique, preserving order.

    Later duplicates of a name get a numeric suffix (`_2`, `_3`, ...). The
    base name is truncated as needed so the suffixed result still fits
    within MAX_IDENTIFIER_LENGTH.
    """
    seen: dict[str, int] = {}
    result: list[str] = []

    for name in names:
        if name not in seen:
            seen[name] = 1
            result.append(name)
            continue

        seen[name] += 1
        suffix = f"_{seen[name]}"
        base = name[: MAX_IDENTIFIER_LENGTH - len(suffix)]
        candidate = f"{base}{suffix}"

        # Extremely unlikely, but if the truncated base+suffix collides with
        # something already produced, keep incrementing until it doesn't.
        while candidate in seen:
            seen[name] += 1
            suffix = f"_{seen[name]}"
            base = name[: MAX_IDENTIFIER_LENGTH - len(suffix)]
            candidate = f"{base}{suffix}"

        seen[candidate] = 1
        result.append(candidate)

    return result


def make_table_name(dataset_id: uuid.UUID) -> str:
    """Deterministic, injection-safe physical table name for a dataset.

    UUID hex digits are the only characters involved, so no sanitization
    is needed - this can never collide and can never contain anything
    unsafe.
    """
    return f"ds_{dataset_id.hex}"
