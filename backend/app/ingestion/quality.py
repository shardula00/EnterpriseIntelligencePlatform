"""Validation rules and the data quality score.

Every rule produces zero or more QualityIssue records with an explicit
`score_impact`; the overall score is just 100 minus the sum of those
impacts (floored at 0). This is deliberately simple and fully transparent -
given the same issues, `compute_quality_score` always gives the same
number, and every deduction is individually inspectable via
GET /datasets/{id}/quality rather than hidden inside one opaque metric.
"""

from dataclasses import dataclass

import pandas as pd

from app.ingestion.profiling import ColumnProfile

HIGH_NULL_RATE_THRESHOLD = 0.20
DUPLICATE_ROWS_MAX_IMPACT = 20.0

ISSUE_WEIGHTS = {
    "empty_column": 15.0,
    "high_null_rate": 5.0,
    "inconsistent_type": 5.0,
    "constant_column": 2.0,
    "duplicate_header": 3.0,
}


@dataclass
class QualityIssue:
    rule: str
    column_name: str | None
    severity: str  # "info" | "warning" | "critical"
    message: str
    score_impact: float


def check_empty_columns(profiles: list[ColumnProfile]) -> list[QualityIssue]:
    return [
        QualityIssue(
            rule="empty_column",
            column_name=p.column_name,
            severity="critical",
            message=f"Column '{p.column_name}' is entirely empty.",
            score_impact=ISSUE_WEIGHTS["empty_column"],
        )
        for p in profiles
        if p.row_count > 0 and p.null_count == p.row_count
    ]


def check_high_null_rate(profiles: list[ColumnProfile]) -> list[QualityIssue]:
    issues = []
    for p in profiles:
        if p.row_count == 0 or p.null_count == p.row_count:
            continue  # empty_column already covers a fully-null column
        null_rate = p.null_count / p.row_count
        if null_rate > HIGH_NULL_RATE_THRESHOLD:
            issues.append(
                QualityIssue(
                    rule="high_null_rate",
                    column_name=p.column_name,
                    severity="warning",
                    message=f"Column '{p.column_name}' is {null_rate:.0%} null.",
                    score_impact=ISSUE_WEIGHTS["high_null_rate"],
                )
            )
    return issues


def check_constant_columns(profiles: list[ColumnProfile]) -> list[QualityIssue]:
    issues = []
    for p in profiles:
        non_null_count = p.row_count - p.null_count
        if non_null_count > 1 and p.distinct_count == 1:
            issues.append(
                QualityIssue(
                    rule="constant_column",
                    column_name=p.column_name,
                    severity="info",
                    message=f"Column '{p.column_name}' has only one distinct value.",
                    score_impact=ISSUE_WEIGHTS["constant_column"],
                )
            )
    return issues


def check_duplicate_rows(df: pd.DataFrame) -> list[QualityIssue]:
    if len(df) == 0:
        return []
    duplicate_count = int(df.duplicated().sum())
    if duplicate_count == 0:
        return []
    ratio = duplicate_count / len(df)
    impact = min(DUPLICATE_ROWS_MAX_IMPACT, round(ratio * 100, 1))
    return [
        QualityIssue(
            rule="duplicate_rows",
            column_name=None,
            severity="warning",
            message=f"{duplicate_count} duplicate row(s) found ({ratio:.1%} of rows).",
            score_impact=impact,
        )
    ]


def check_type_coercion_loss(coercion_null_counts: dict[str, int]) -> list[QualityIssue]:
    return [
        QualityIssue(
            rule="inconsistent_type",
            column_name=column,
            severity="warning",
            message=(
                f"{count} value(s) in '{column}' didn't match the detected "
                "column type and were set to null."
            ),
            score_impact=ISSUE_WEIGHTS["inconsistent_type"],
        )
        for column, count in coercion_null_counts.items()
        if count > 0
    ]


def check_duplicate_headers(duplicate_original_headers: list[str]) -> list[QualityIssue]:
    return [
        QualityIssue(
            rule="duplicate_header",
            column_name=None,
            severity="warning",
            message=f"Header '{name}' appeared more than once in the source file.",
            score_impact=ISSUE_WEIGHTS["duplicate_header"],
        )
        for name in duplicate_original_headers
    ]


def run_quality_checks(
    df: pd.DataFrame,
    profiles: list[ColumnProfile],
    coercion_null_counts: dict[str, int],
    duplicate_original_headers: list[str],
) -> list[QualityIssue]:
    """Run every validation rule and return the combined issue list."""
    return [
        *check_empty_columns(profiles),
        *check_high_null_rate(profiles),
        *check_constant_columns(profiles),
        *check_duplicate_rows(df),
        *check_type_coercion_loss(coercion_null_counts),
        *check_duplicate_headers(duplicate_original_headers),
    ]


def compute_quality_score(issues: list[QualityIssue]) -> float:
    """100 minus the sum of every issue's score_impact, floored at 0."""
    total_deduction = sum(issue.score_impact for issue in issues)
    return round(max(0.0, 100.0 - total_deduction), 1)
