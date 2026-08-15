"""Deterministic natural-language -> query-intent parsing. No LLM call, no
network, no model download - same zero-cost-by-default precedent as
app/rag/embeddings.py's "hashing" provider and app/rag/llm.py's
"local_extractive" provider, and a stronger safety property besides: since
a question can only ever resolve to one of the four closed-set `kind`
values below (never free-form SQL text), app/analytics/query_builder.py has
no code path that could build anything other than a read-only SELECT
against the asked-about dataset's own table.

Every column this module can ever point to comes from the dataset's *real*,
already-detected `DatasetColumn` rows (see app/models/dataset.py) - nothing
here hardcodes a business column name like "revenue" or "region". A small
synonym table maps common business phrasing (e.g. "sales") onto the kind of
words a column name might actually use - that's about natural language
being loose, not about any specific dataset.

Supported question shapes (see EVAL_CASES-style docstring in
tests/analytics/test_nl_parser.py for concrete examples):
    - total / sum of <metric>                              -> "total"
    - average / count / highest / lowest of <metric>        -> "total"
    - <total|average|...> <metric> by/per <category>        -> "breakdown"
    - which <category> ... highest/lowest <metric>           -> "top_n"
    - top N <category> by <metric>                           -> "top_n"
    - monthly/weekly/daily <metric> (trend, over time)       -> "trend"

Deliberately NOT supported in this first version: filtering ("revenue in
the West region"), multi-metric questions, comparisons across two
datasets. An unrecognized question raises UnsupportedQuestionError rather
than guessing - a wrong SQL query silently returning misleading numbers
would be far worse than an honest "I don't understand this question yet."
"""

import re
from dataclasses import dataclass

from app.analytics.errors import UnsupportedQuestionError
from app.models.dataset import DatasetColumn

NUMERIC_TYPES = {"integer", "float"}
CATEGORICAL_TYPES = {"text", "boolean"}

AGGREGATIONS = ("sum", "avg", "count", "min", "max")

# Ordered so a more specific phrase (checked first) wins over a shorter one
# that could also match inside it (e.g. "highest" before a bare "high").
_AGG_PHRASES: list[tuple[str, str]] = [
    ("sum", "total"),
    ("sum", "sum of"),
    ("sum", "sum"),
    ("avg", "average"),
    ("avg", "avg"),
    ("avg", "mean"),
    ("max", "highest"),
    ("max", "maximum"),
    ("max", "largest"),
    ("max", "greatest"),
    ("max", "most"),
    ("max", "max"),
    ("min", "lowest"),
    ("min", "minimum"),
    ("min", "smallest"),
    ("min", "least"),
    ("min", "min"),
    ("count", "how many"),
    ("count", "number of"),
    ("count", "count of"),
    ("count", "count"),
]

_GRANULARITY_PHRASES: list[tuple[str, str]] = [
    ("day", "daily"),
    ("day", "by day"),
    ("day", "per day"),
    ("week", "weekly"),
    ("week", "by week"),
    ("week", "per week"),
    ("month", "monthly"),
    ("month", "by month"),
    ("month", "per month"),
]
_GENERIC_TREND_PHRASES = ("trend", "over time")

_BREAKDOWN_PHRASES = (" by ", " per ", " for each ", " across ")
_WHICH_PHRASE = "which "
_TOP_N_PATTERN = re.compile(r"\btop\s+(\d+)\b")

# Small, generic business-terminology synonyms - natural language rarely
# uses a column's exact name. Not dataset-specific: these are common
# English business words, applicable to any dataset that happens to use
# them, not a lookup table of this project's own fixture column names.
_SYNONYMS: dict[str, list[str]] = {
    "revenue": ["sales", "sale", "income", "turnover"],
    "cost": ["costs", "expense", "expenses", "spend"],
    "profit": ["margin", "earnings"],
    "quantity": ["qty", "units", "volume"],
    "price": ["cost", "amount"],
    "customer": ["client", "account"],
    "product": ["item"],
    "region": ["area", "territory", "location"],
    "category": ["type", "segment"],
    "date": ["time", "period"],
}


@dataclass
class ParsedIntent:
    kind: str  # "total" | "breakdown" | "top_n" | "trend"
    aggregation: str  # one of AGGREGATIONS
    metric_column: str | None  # None only when aggregation == "count"
    group_by_column: str | None = None  # "breakdown" / "top_n"
    date_column: str | None = None  # "trend"
    granularity: str | None = None  # "trend": "day" | "week" | "month"
    limit: int | None = None  # "top_n"
    descending: bool = True  # "top_n" order direction


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _stem(word: str) -> str:
    """Crude English stemmer: strip a trailing plural 's' - good enough to
    match a question's "products"/"regions" against a dataset's own
    singular column names without a stemming library dependency. Not
    applied to short words (avoids "as" -> "a", "is" -> "i") or words
    already ending "ss" (avoids "class" -> "clas")."""
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _expand_with_stems(words: set[str]) -> set[str]:
    return words | {_stem(w) for w in words}


def _column_tokens(column: DatasetColumn) -> set[str]:
    """Every word a column's name is 'about', including its synonyms and
    stems - the original header (e.g. "Total Revenue"), the sanitized name
    (e.g. "total_revenue"), each token's synonym expansions, and each
    resulting word's singular stem."""
    words = set(_tokenize(column.original_name)) | set(_tokenize(column.column_name))
    expanded = set(words)
    for word in words:
        expanded.update(_SYNONYMS.get(word, []))
    return _expand_with_stems(expanded)


def _find_agg(question: str) -> str | None:
    for aggregation, phrase in _AGG_PHRASES:
        if phrase in question:
            return aggregation
    return None


def _best_column_match(
    question_tokens: set[str], candidates: list[DatasetColumn]
) -> DatasetColumn | None:
    """The candidate column whose name/synonym tokens overlap the question
    the most - None if nothing overlaps at all. Ties broken by declared
    column order (first wins), for deterministic results."""
    best: DatasetColumn | None = None
    best_score = 0
    for column in candidates:
        score = len(_column_tokens(column) & question_tokens)
        if score > best_score:
            best, best_score = column, score
    return best


def parse(question: str, columns: list[DatasetColumn]) -> ParsedIntent:
    """Parse a natural-language question into a ParsedIntent, using only
    the dataset's real columns. Raises UnsupportedQuestionError if no
    confident match is found."""
    normalized = f" {question.strip().lower()} "
    normalized = re.sub(r"\s+", " ", normalized)
    tokens = _expand_with_stems(set(_tokenize(normalized)))
    if not tokens:
        raise UnsupportedQuestionError("The question is empty.")

    numeric_columns = [c for c in columns if c.detected_type in NUMERIC_TYPES]
    categorical_columns = [c for c in columns if c.detected_type in CATEGORICAL_TYPES]
    date_columns = [c for c in columns if c.detected_type == "datetime"]

    # --- Trend: "monthly sales", "sales trend", "revenue over time" -------
    granularity = next((g for g, phrase in _GRANULARITY_PHRASES if phrase in normalized), None)
    is_generic_trend = any(phrase in normalized for phrase in _GENERIC_TREND_PHRASES)
    if (granularity or is_generic_trend) and date_columns:
        date_column = date_columns[0] if len(date_columns) == 1 else _best_column_match(
            tokens, date_columns
        )
        metric = _best_column_match(tokens, numeric_columns)
        if date_column is not None and metric is not None:
            return ParsedIntent(
                kind="trend",
                aggregation="sum",
                metric_column=metric.column_name,
                date_column=date_column.column_name,
                granularity=granularity or "month",
            )

    aggregation = _find_agg(normalized) or "sum"
    metric = None if aggregation == "count" else _best_column_match(tokens, numeric_columns)
    if aggregation != "count" and metric is None:
        raise UnsupportedQuestionError(
            "Could not identify which numeric column this question is about."
        )

    # --- "which <category> ... highest/lowest <metric>" -> top_n ----------
    # Superlative words ("highest"/"lowest") describe *ranking direction*,
    # not a literal per-row MAX/MIN - "which product generated the highest
    # revenue" means "rank products by total revenue, take the top one,"
    # not "find the single highest revenue row." sum/avg, if that's what
    # was actually said (e.g. "highest average revenue"), keep their own
    # meaning as the ranking metric.
    ranking_aggregation = "sum" if aggregation in ("count", "max", "min") else aggregation
    descending = not any(phrase in normalized for agg, phrase in _AGG_PHRASES if agg == "min")

    # metric is required here: ranking_aggregation is always "sum"/"avg" (a
    # top_n never ranks by a bare COUNT column), so a top_n with no
    # identified metric column would be a broken query - skip to breakdown/
    # total below instead of returning one.
    if _WHICH_PHRASE in normalized and metric is not None:
        group_by = _best_column_match(tokens, categorical_columns)
        if group_by is not None:
            return ParsedIntent(
                kind="top_n",
                aggregation=ranking_aggregation,
                metric_column=metric.column_name,
                group_by_column=group_by.column_name,
                limit=1,
                descending=descending,
            )

    # --- "top N <category> by <metric>" -> top_n ---------------------------
    top_n_match = _TOP_N_PATTERN.search(normalized)
    if top_n_match and metric is not None:
        group_by = _best_column_match(tokens, categorical_columns)
        if group_by is not None:
            return ParsedIntent(
                kind="top_n",
                aggregation=ranking_aggregation,
                metric_column=metric.column_name,
                group_by_column=group_by.column_name,
                limit=int(top_n_match.group(1)),
                descending=descending,
            )

    # --- "<agg> <metric> by/per <category>" -> breakdown --------------------
    if any(phrase in normalized for phrase in _BREAKDOWN_PHRASES):
        group_by = _best_column_match(tokens, categorical_columns)
        if group_by is not None:
            return ParsedIntent(
                kind="breakdown",
                aggregation=aggregation,
                metric_column=metric.column_name if metric else None,
                group_by_column=group_by.column_name,
            )

    # --- Otherwise: a single aggregate value over the whole dataset --------
    return ParsedIntent(
        kind="total",
        aggregation=aggregation,
        metric_column=metric.column_name if metric else None,
    )
