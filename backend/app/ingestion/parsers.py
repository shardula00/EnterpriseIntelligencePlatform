"""Turns uploaded file bytes into a pandas DataFrame.

One function per supported format, plus a dispatcher. Deliberately narrow:
CSV and Excel are expected to be a single flat table; JSON is expected to
be a list of flat (non-nested) objects. Anything else is a documented
limitation (see backend/README.md), not a silent best-effort guess.
"""

import io
import json

import pandas as pd

from app.ingestion.errors import EmptyFileError, ParseError, UnsupportedFileTypeError

SUPPORTED_EXTENSIONS = {"csv", "xlsx", "json"}


def parse_csv(content: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:  # pandas raises several distinct error types
        raise ParseError(f"Could not parse file as CSV: {exc}") from exc
    return df


def parse_excel(content: bytes) -> pd.DataFrame:
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise ParseError(f"Could not parse file as Excel (.xlsx): {exc}") from exc
    return df


def parse_json(content: bytes) -> pd.DataFrame:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Could not parse file as JSON: {exc}") from exc

    if not isinstance(payload, list):
        raise ParseError(
            "JSON upload must be a list of flat objects (e.g. "
            '`[{"col": "value"}, ...]`), got a top-level '
            f"{type(payload).__name__}."
        )
    if payload and not all(isinstance(item, dict) for item in payload):
        raise ParseError("JSON upload must be a list of objects, not mixed/scalar values.")

    try:
        df = pd.DataFrame(payload)
    except Exception as exc:
        raise ParseError(f"Could not convert JSON records into a table: {exc}") from exc
    return df


_PARSERS = {
    "csv": parse_csv,
    "xlsx": parse_excel,
    "json": parse_json,
}


def extension_from_filename(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def parse_upload(filename: str, content: bytes) -> pd.DataFrame:
    """Dispatch to the right parser based on file extension, then validate shape."""
    extension = extension_from_filename(filename)
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '.{extension}'. Supported types: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    if not content:
        raise EmptyFileError("Uploaded file is empty.")

    df = _PARSERS[extension](content)

    if df.shape[1] == 0:
        raise EmptyFileError("File has no columns.")
    if df.shape[0] == 0:
        raise EmptyFileError("File has no data rows.")

    return df
