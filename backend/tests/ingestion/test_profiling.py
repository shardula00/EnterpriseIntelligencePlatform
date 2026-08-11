import pandas as pd

from app.ingestion.profiling import profile_column, profile_dataframe


def test_profile_integer_column():
    # Mirrors what coerce_dataframe() actually produces for an "integer"
    # column: pandas' nullable Int64 dtype, not a plain float64 upcast.
    series = pd.Series([10, 20, 30, None], name="amount", dtype="Int64")
    profile = profile_column(series, "integer")

    assert profile.column_name == "amount"
    assert profile.row_count == 4
    assert profile.null_count == 1
    assert profile.distinct_count == 3
    assert profile.min_value == "10"
    assert profile.max_value == "30"
    assert profile.mean_value == 20.0


def test_profile_text_column_samples_are_deduplicated_and_capped():
    series = pd.Series(["a", "a", "b", "c", "d"], name="letter")
    profile = profile_column(series, "text")

    assert profile.distinct_count == 4
    assert len(profile.sample_values) == 3  # capped at MAX_SAMPLE_VALUES


def test_profile_empty_column_has_no_min_max_mean():
    series = pd.Series([None, None, None], name="empty_col")
    profile = profile_column(series, "text")

    assert profile.null_count == 3
    assert profile.distinct_count == 0
    assert profile.min_value is None
    assert profile.max_value is None
    assert profile.mean_value is None
    assert profile.sample_values == []


def test_profile_dataframe_covers_every_column():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    profiles = profile_dataframe(df, {"a": "integer", "b": "text"})

    assert [p.column_name for p in profiles] == ["a", "b"]
    assert [p.detected_type for p in profiles] == ["integer", "text"]


def test_long_text_value_is_truncated():
    series = pd.Series(["x" * 500], name="notes")
    profile = profile_column(series, "text")

    assert len(profile.max_value) == 200
