"""Verified-relationship what-if scenario engine.

Reuses app.analytics.query_builder directly for real baseline totals -
the exact same "total"+"sum" query shape app/analytics/service.py already
builds, just invoked here without going through nl_parser (this module
already knows which columns it means once matched). Never re-implements
SQL aggregation.

Before applying any percentage delta through a relationship between two
metrics, that relationship is EMPIRICALLY VERIFIED against the dataset's
actual rows - never a hardcoded business rule like "profit = revenue -
cost". This is the same "verify, don't assume" discipline
app/kg/entity_extraction.py already applies to relationship data: a
functional dependency is only ever used here if it's checked, row by row,
against the real physical table. If no such relationship can be verified
for the metrics named in the question, run_scenario() honestly declines
rather than inventing a number.

Deliberately NOT a causal or predictive model: every computed result is a
linear extrapolation over already-observed historical totals, and says so
explicitly in its own `note`.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.nl_parser import ParsedIntent
from app.analytics.query_builder import build_query
from app.config import Settings
from app.ingestion.table_builder import build_dataset_table
from app.models.dataset import Dataset, DatasetColumn

NUMERIC_TYPES = {"integer", "float"}

# A relationship is only "verified" if it holds (within tolerance) for at
# least this fraction of rows that have all three values present -
# real-world data can have a stray bad row without the relationship being
# false.
_MATCH_RATIO_THRESHOLD = 0.99
_RELATIVE_TOLERANCE = 0.01  # 1% of the affected value's own magnitude

_INCREASE_WORDS = ("increase", "increases", "rise", "rises", "grow", "grows", "goes up", "higher", "up by")
_DECREASE_WORDS = ("decrease", "decreases", "drop", "drops", "fall", "falls", "goes down", "lower", "down by")
_PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _best_numeric_match(tokens: set[str], candidates: list[DatasetColumn]) -> DatasetColumn | None:
    """Same small "overlap the question's words against a column's own
    name" heuristic every other Phase 8/9 module independently
    re-implements for itself (see app/analytics/nl_parser.py,
    app/kg/entity_extraction.py) - deliberately not imported from either,
    per this project's established "each module owns its own tiny
    heuristic" convention."""
    best: DatasetColumn | None = None
    best_score = 0
    for column in candidates:
        column_tokens = _tokenize(column.original_name) | _tokenize(column.column_name)
        score = len(column_tokens & tokens)
        if score > best_score:
            best, best_score = column, score
    return best


@dataclass
class ScenarioResult:
    computed: bool
    question: str
    affected_metric: str | None = None
    perturbed_metric: str | None = None
    delta_percent: float | None = None
    baseline_perturbed_value: float | None = None
    baseline_affected_value: float | None = None
    new_perturbed_value: float | None = None
    new_affected_value: float | None = None
    affected_value_change: float | None = None
    relationship: str | None = None
    note: str | None = None
    reason: str | None = None  # populated only when computed is False


def _parse_question(
    question: str, numeric_columns: list[DatasetColumn]
) -> tuple[DatasetColumn, DatasetColumn, float] | None:
    """Extracts (affected_metric, perturbed_metric, signed_delta_percent)
    from a "what happens to X if Y <increases/decreases> by N%" - style
    question, or None if any part can't be confidently identified.
    Deliberately conservative: this never guesses a metric that isn't a
    real column."""
    lowered = question.lower()

    percent_match = _PERCENT_PATTERN.search(lowered)
    if not percent_match:
        return None
    percent = float(percent_match.group(1))
    if any(word in lowered for word in _DECREASE_WORDS):
        percent = -abs(percent)
    elif any(word in lowered for word in _INCREASE_WORDS):
        percent = abs(percent)
    else:
        return None

    if " if " in lowered:
        before, after = lowered.split(" if ", 1)
    else:
        before, after = lowered, lowered

    affected = _best_numeric_match(_tokenize(before), numeric_columns)
    perturbed = _best_numeric_match(_tokenize(after), numeric_columns)
    if affected is None or perturbed is None or affected.column_name == perturbed.column_name:
        return None
    return affected, perturbed, percent


def _get_total(
    db: Session, dataset: Dataset, columns: list[DatasetColumn], column_name: str, max_rows: int
) -> float:
    intent = ParsedIntent(kind="total", aggregation="sum", metric_column=column_name)
    built = build_query(dataset, columns, intent, max_rows)
    row = db.connection().execute(built.statement).one()
    value = row._mapping[column_name]
    return float(value) if value is not None else 0.0


def _verify_relationship(
    db: Session,
    dataset: Dataset,
    columns: list[DatasetColumn],
    affected: DatasetColumn,
    perturbed: DatasetColumn,
    others: list[DatasetColumn],
) -> tuple[DatasetColumn, str, str] | None:
    """Checks, row by row against the real physical table, whether
    affected = perturbed +/- other holds for any other numeric column.
    Returns (other_column, symbol, relationship_description) for the
    first verified match, or None if nothing verifies - never a guess."""
    column_map = {c.column_name: c.detected_type for c in columns}
    table = build_dataset_table(dataset.storage_table_name, column_map)

    for other in others:
        stmt = select(
            table.c[affected.column_name], table.c[perturbed.column_name], table.c[other.column_name]
        )
        rows = db.connection().execute(stmt).all()
        if not rows:
            continue

        for compute_expected, symbol in ((lambda p, o: p - o, "-"), (lambda p, o: p + o, "+")):
            checked = 0
            matches = 0
            for affected_v, perturbed_v, other_v in rows:
                if affected_v is None or perturbed_v is None or other_v is None:
                    continue
                checked += 1
                expected = compute_expected(float(perturbed_v), float(other_v))
                scale = max(abs(float(affected_v)), 1.0)
                if abs(float(affected_v) - expected) <= _RELATIVE_TOLERANCE * scale:
                    matches += 1
            if checked > 0 and matches / checked >= _MATCH_RATIO_THRESHOLD:
                relationship = f"{affected.column_name} = {perturbed.column_name} {symbol} {other.column_name}"
                return other, symbol, relationship

    return None


def run_scenario(
    db: Session, settings: Settings, dataset: Dataset, columns: list[DatasetColumn], question: str
) -> ScenarioResult:
    numeric_columns = [c for c in columns if c.detected_type in NUMERIC_TYPES]

    parsed = _parse_question(question, numeric_columns)
    if parsed is None:
        return ScenarioResult(
            computed=False,
            question=question,
            reason=(
                "Could not identify a percentage change and two numeric metrics "
                "(an affected metric and a perturbed metric) in this question."
            ),
        )
    affected, perturbed, delta_percent = parsed

    others = [c for c in numeric_columns if c.column_name not in (affected.column_name, perturbed.column_name)]
    verification = _verify_relationship(db, dataset, columns, affected, perturbed, others)
    if verification is None:
        return ScenarioResult(
            computed=False,
            question=question,
            affected_metric=affected.column_name,
            perturbed_metric=perturbed.column_name,
            delta_percent=delta_percent,
            reason=(
                f"No verified relationship between '{affected.column_name}' and "
                f"'{perturbed.column_name}' could be found in the actual dataset - "
                "declining to fabricate an impact estimate."
            ),
        )
    other_column, symbol, relationship = verification

    max_rows = settings.analytics_max_result_rows
    baseline_perturbed = _get_total(db, dataset, columns, perturbed.column_name, max_rows)
    baseline_affected = _get_total(db, dataset, columns, affected.column_name, max_rows)
    baseline_other = _get_total(db, dataset, columns, other_column.column_name, max_rows)

    new_perturbed = baseline_perturbed * (1 + delta_percent / 100)
    new_affected = new_perturbed + baseline_other if symbol == "+" else new_perturbed - baseline_other

    return ScenarioResult(
        computed=True,
        question=question,
        affected_metric=affected.column_name,
        perturbed_metric=perturbed.column_name,
        delta_percent=delta_percent,
        baseline_perturbed_value=baseline_perturbed,
        baseline_affected_value=baseline_affected,
        new_perturbed_value=new_perturbed,
        new_affected_value=new_affected,
        affected_value_change=new_affected - baseline_affected,
        relationship=relationship,
        note=(
            f"This is a linear extrapolation using the verified relationship "
            f"'{relationship}' over historical totals, not a causal or predictive "
            f"model. Assumes '{other_column.column_name}' remains unchanged."
        ),
    )
