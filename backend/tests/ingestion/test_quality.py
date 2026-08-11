import pandas as pd

from app.ingestion.profiling import ColumnProfile
from app.ingestion.quality import (
    check_constant_columns,
    check_duplicate_headers,
    check_duplicate_rows,
    check_empty_columns,
    check_high_null_rate,
    check_type_coercion_loss,
    compute_quality_score,
    run_quality_checks,
)


def _profile(
    column_name: str,
    detected_type: str = "text",
    row_count: int = 10,
    null_count: int = 0,
    distinct_count: int = 5,
) -> ColumnProfile:
    return ColumnProfile(
        column_name=column_name,
        detected_type=detected_type,
        row_count=row_count,
        null_count=null_count,
        distinct_count=distinct_count,
        min_value=None,
        max_value=None,
        mean_value=None,
        sample_values=[],
    )


def test_check_empty_columns_flags_fully_null_column():
    profiles = [_profile("a", row_count=10, null_count=10, distinct_count=0)]
    issues = check_empty_columns(profiles)
    assert len(issues) == 1
    assert issues[0].rule == "empty_column"
    assert issues[0].column_name == "a"


def test_check_empty_columns_ignores_partially_null_column():
    profiles = [_profile("a", row_count=10, null_count=5, distinct_count=3)]
    assert check_empty_columns(profiles) == []


def test_check_high_null_rate_flags_above_threshold():
    profiles = [_profile("a", row_count=10, null_count=3, distinct_count=3)]  # 30%
    issues = check_high_null_rate(profiles)
    assert len(issues) == 1
    assert issues[0].rule == "high_null_rate"


def test_check_high_null_rate_ignores_below_threshold():
    profiles = [_profile("a", row_count=10, null_count=1, distinct_count=5)]  # 10%
    assert check_high_null_rate(profiles) == []


def test_check_high_null_rate_does_not_double_flag_empty_column():
    profiles = [_profile("a", row_count=10, null_count=10, distinct_count=0)]
    assert check_high_null_rate(profiles) == []


def test_check_constant_columns_flags_single_distinct_value():
    profiles = [_profile("a", row_count=10, null_count=0, distinct_count=1)]
    issues = check_constant_columns(profiles)
    assert len(issues) == 1
    assert issues[0].rule == "constant_column"


def test_check_duplicate_rows_detects_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    issues = check_duplicate_rows(df)
    assert len(issues) == 1
    assert issues[0].rule == "duplicate_rows"


def test_check_duplicate_rows_none_when_all_unique():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    assert check_duplicate_rows(df) == []


def test_check_type_coercion_loss_flags_nonzero_counts():
    issues = check_type_coercion_loss({"amount": 2, "clean_col": 0})
    assert len(issues) == 1
    assert issues[0].column_name == "amount"


def test_check_duplicate_headers_one_issue_per_name():
    issues = check_duplicate_headers(["Total", "Total"])
    assert len(issues) == 2
    assert all(issue.rule == "duplicate_header" for issue in issues)


def test_compute_quality_score_no_issues_is_100():
    assert compute_quality_score([]) == 100.0


def test_compute_quality_score_deducts_exactly_the_weights():
    profiles = [
        _profile("empty_col", row_count=10, null_count=10, distinct_count=0),
        _profile("noisy_col", row_count=10, null_count=3, distinct_count=3),
    ]
    issues = run_quality_checks(
        df=pd.DataFrame({"empty_col": [None] * 10, "noisy_col": list(range(10))}),
        profiles=profiles,
        coercion_null_counts={},
        duplicate_original_headers=[],
    )
    score = compute_quality_score(issues)
    # empty_column (15.0) + high_null_rate (5.0) = 20.0 deducted from 100.
    assert score == 80.0


def test_compute_quality_score_never_goes_below_zero():
    profiles = [
        _profile(f"col_{i}", row_count=10, null_count=10, distinct_count=0) for i in range(10)
    ]
    issues = run_quality_checks(
        df=pd.DataFrame({f"col_{i}": [None] * 10 for i in range(10)}),
        profiles=profiles,
        coercion_null_counts={},
        duplicate_original_headers=[],
    )
    assert compute_quality_score(issues) == 0.0
