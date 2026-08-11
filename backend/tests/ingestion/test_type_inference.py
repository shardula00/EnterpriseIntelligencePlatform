import pandas as pd

from app.ingestion.type_inference import coerce_dataframe, detect_column_type, detect_column_types


def test_native_integer_column():
    assert detect_column_type(pd.Series([1, 2, 3])) == "integer"


def test_native_float_column():
    assert detect_column_type(pd.Series([1.5, 2.5, None])) == "float"


def test_native_bool_column():
    assert detect_column_type(pd.Series([True, False, True])) == "boolean"


def test_string_column_of_integers_is_detected_as_integer():
    assert detect_column_type(pd.Series(["1", "2", "3", "4"])) == "integer"


def test_string_column_of_floats_is_detected_as_float():
    assert detect_column_type(pd.Series(["1.1", "2.2", "3.3"])) == "float"


def test_string_column_of_dates_is_detected_as_datetime():
    series = pd.Series(["2024-01-01", "2024-02-15", "2024-03-30"])
    assert detect_column_type(series) == "datetime"


def test_plain_text_column_is_detected_as_text():
    series = pd.Series(["apple", "banana", "cherry"])
    assert detect_column_type(series) == "text"


def test_mostly_numeric_with_one_bad_value_is_still_numeric():
    # 5/6 = 0.833 < threshold, so this should NOT be numeric.
    series = pd.Series(["1", "2", "3", "4", "5", "not-a-number"])
    assert detect_column_type(series) == "text"


def test_almost_all_numeric_above_threshold_is_numeric():
    # 99 good values + 1 bad value out of 100 = 0.99 >= 0.98 threshold.
    values = [str(i) for i in range(99)] + ["oops"]
    series = pd.Series(values)
    assert detect_column_type(series) == "integer"


def test_empty_column_defaults_to_text():
    series = pd.Series([None, None, None])
    assert detect_column_type(series) == "text"


def test_detect_column_types_maps_every_column():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    types = detect_column_types(df)
    assert types == {"a": "integer", "b": "text"}


def test_coerce_dataframe_converts_string_numbers_to_integer():
    df = pd.DataFrame({"amount": ["10", "20", "30"]})
    coerced, coercion_losses = coerce_dataframe(df, {"amount": "integer"})

    assert coerced["amount"].tolist() == [10, 20, 30]
    assert coercion_losses == {}


def test_coerce_dataframe_flags_values_lost_to_coercion():
    values = [str(i) for i in range(99)] + ["oops"]
    df = pd.DataFrame({"amount": values})
    coerced, coercion_losses = coerce_dataframe(df, {"amount": "integer"})

    assert coercion_losses == {"amount": 1}
    assert coerced["amount"].isna().sum() == 1


def test_coerce_dataframe_datetime():
    df = pd.DataFrame({"when": ["2024-01-01", "2024-02-01"]})
    coerced, _ = coerce_dataframe(df, {"when": "datetime"})
    assert pd.api.types.is_datetime64_any_dtype(coerced["when"])


def test_coerce_dataframe_text_strips_whitespace_and_preserves_nulls():
    df = pd.DataFrame({"name": ["  Alice  ", None, "Bob"]})
    coerced, coercion_losses = coerce_dataframe(df, {"name": "text"})

    assert coerced["name"].tolist()[0] == "Alice"
    assert pd.isna(coerced["name"].tolist()[1])
    assert coerced["name"].tolist()[2] == "Bob"
    assert coercion_losses == {}
