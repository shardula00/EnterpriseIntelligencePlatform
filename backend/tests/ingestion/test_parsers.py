import io

import pandas as pd
import pytest

from app.ingestion.errors import EmptyFileError, ParseError, UnsupportedFileTypeError
from app.ingestion.parsers import extension_from_filename, parse_upload


def _csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def test_extension_from_filename():
    assert extension_from_filename("orders.csv") == "csv"
    assert extension_from_filename("Orders.XLSX") == "xlsx"
    assert extension_from_filename("noextension") == ""


def test_parse_csv_upload():
    content = _csv_bytes("name,amount\nAlice,10\nBob,20\n")
    df = parse_upload("orders.csv", content)

    assert list(df.columns) == ["name", "amount"]
    assert len(df) == 2


def test_parse_excel_upload():
    df_in = pd.DataFrame({"name": ["Alice", "Bob"], "amount": [10, 20]})
    buffer = io.BytesIO()
    df_in.to_excel(buffer, index=False, engine="openpyxl")

    df = parse_upload("orders.xlsx", buffer.getvalue())

    assert list(df.columns) == ["name", "amount"]
    assert len(df) == 2


def test_parse_json_upload():
    content = b'[{"name": "Alice", "amount": 10}, {"name": "Bob", "amount": 20}]'
    df = parse_upload("orders.json", content)

    assert list(df.columns) == ["name", "amount"]
    assert len(df) == 2


def test_unsupported_extension_raises():
    with pytest.raises(UnsupportedFileTypeError):
        parse_upload("orders.txt", b"name,amount\nAlice,10\n")


def test_empty_file_raises():
    with pytest.raises(EmptyFileError):
        parse_upload("orders.csv", b"")


def test_header_only_csv_raises_empty_file():
    with pytest.raises(EmptyFileError):
        parse_upload("orders.csv", _csv_bytes("name,amount\n"))


def test_malformed_json_raises_parse_error():
    with pytest.raises(ParseError):
        parse_upload("orders.json", b"{not valid json")


def test_json_scalar_top_level_raises_parse_error():
    with pytest.raises(ParseError):
        parse_upload("orders.json", b'"just a string"')


def test_malformed_excel_raises_parse_error():
    with pytest.raises(ParseError):
        parse_upload("orders.xlsx", b"this is not a real xlsx file")
