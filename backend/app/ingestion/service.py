"""Orchestrates the full ingestion pipeline and the dataset read/delete paths.

Pipeline order implemented here (see backend/README.md for the full
rationale): parse -> validate -> detect schema -> transform/coerce ->
profile -> quality score -> load into Postgres -> persist metadata +
lineage, all inside one DB transaction. Profiling runs on the *coerced*
data (not the raw upload) because computing a mean/min/max on a column
that's still raw strings would either crash or be meaningless - by the
time we profile, the column already has its real numeric/datetime dtype.
Quality scoring happens before the Postgres write (not after, despite
"quality report" being described after "PostgreSQL" in the pipeline
narrative) specifically so that a dataset row, its quality report, and its
data table are always written together, atomically - never a dataset
recorded without its data, or data loaded without a quality report.
"""

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingestion.errors import DatasetNotFoundError, FileTooLargeError
from app.ingestion.naming import dedupe_identifiers, make_table_name, sanitize_identifier
from app.ingestion.parsers import extension_from_filename, parse_upload
from app.ingestion.profiling import profile_dataframe
from app.ingestion.quality import compute_quality_score, run_quality_checks
from app.ingestion.table_builder import (
    INGESTED_SCHEMA,
    build_dataset_table,
    create_and_load,
    dataframe_to_records,
    drop_dataset_table,
    fetch_preview_rows,
)
from app.ingestion.type_inference import coerce_dataframe, detect_column_types
from app.models.dataset import Dataset, DatasetColumn, DatasetLineageEvent, DatasetQualityIssue

DEFAULT_PREVIEW_LIMIT = 20


def _find_duplicate_originals(
    original_headers: list[str], sanitized_headers: list[str]
) -> list[str]:
    """Original header names whose sanitized form collided with an earlier one."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for original, sanitized in zip(original_headers, sanitized_headers, strict=True):
        if sanitized in seen:
            duplicates.append(original)
        else:
            seen.add(sanitized)
    return duplicates


def _retain_raw_file(
    settings: Settings, dataset_id: uuid.UUID, filename: str, content: bytes
) -> str | None:
    """Save the original upload for provenance. Best-effort: a failure here
    degrades lineage, it doesn't abort ingestion."""
    safe_name = Path(filename).name or "upload"
    storage_filename = f"{dataset_id.hex}_{safe_name}"
    try:
        settings.upload_storage_dir.mkdir(parents=True, exist_ok=True)
        (settings.upload_storage_dir / storage_filename).write_bytes(content)
    except OSError:
        return None
    return storage_filename


def ingest_upload(
    db: Session,
    settings: Settings,
    filename: str,
    content: bytes,
    dataset_name: str | None = None,
) -> Dataset:
    """Run the full pipeline for one uploaded file and persist the result.

    Raises an IngestionError subclass (see errors.py) on any failure before
    the database write - in that case nothing is persisted. Any failure
    during/after the database write propagates as a normal exception and
    the transaction is rolled back by the caller's session lifecycle.
    """
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise FileTooLargeError(
            f"File is {len(content) / (1024 * 1024):.1f}MB, exceeding the "
            f"{settings.max_upload_size_mb}MB upload limit."
        )

    dataset_id = uuid.uuid4()
    events: list[DatasetLineageEvent] = []

    def record(step: str, detail: dict | None = None) -> None:
        events.append(
            DatasetLineageEvent(dataset_id=dataset_id, step=step, status="success", detail=detail)
        )

    record("upload_received", {"filename": filename, "size_bytes": len(content)})

    df = parse_upload(filename, content)
    record("validated", {"row_count": int(df.shape[0]), "column_count": int(df.shape[1])})

    original_headers = [str(c) for c in df.columns]
    sanitized_headers = [sanitize_identifier(h) for h in original_headers]
    duplicate_original_headers = _find_duplicate_originals(original_headers, sanitized_headers)
    column_names = dedupe_identifiers(sanitized_headers)
    df.columns = column_names

    detected_types = detect_column_types(df)
    record("schema_detected", {"columns": detected_types})

    coerced_df, coercion_null_counts = coerce_dataframe(df, detected_types)
    record("transformed", {"values_nulled_by_coercion": coercion_null_counts})

    profiles = profile_dataframe(coerced_df, detected_types)
    record("profiled", {"columns_profiled": len(profiles)})

    issues = run_quality_checks(
        coerced_df, profiles, coercion_null_counts, duplicate_original_headers
    )
    score = compute_quality_score(issues)
    record("quality_scored", {"score": score, "issue_count": len(issues)})

    table_name = make_table_name(dataset_id)
    table = build_dataset_table(table_name, detected_types)
    records = dataframe_to_records(coerced_df)

    connection = db.connection()
    create_and_load(connection, table, records)
    source_file_path = _retain_raw_file(settings, dataset_id, filename, content)
    record("loaded", {"table": f"{INGESTED_SCHEMA}.{table_name}", "rows_loaded": len(records)})

    dataset = Dataset(
        id=dataset_id,
        name=dataset_name or Path(filename).stem,
        original_filename=filename,
        file_type=extension_from_filename(filename),
        storage_schema=INGESTED_SCHEMA,
        storage_table_name=table_name,
        row_count=len(coerced_df),
        column_count=len(column_names),
        quality_score=score,
        status="ready",
        source_file_path=source_file_path,
        columns=[
            DatasetColumn(
                dataset_id=dataset_id,
                position=i,
                original_name=original_headers[i],
                column_name=column_names[i],
                detected_type=detected_types[column_names[i]],
                nullable=True,
                null_count=profiles[i].null_count,
                distinct_count=profiles[i].distinct_count,
                min_value=profiles[i].min_value,
                max_value=profiles[i].max_value,
                mean_value=profiles[i].mean_value,
                sample_values=profiles[i].sample_values,
            )
            for i in range(len(column_names))
        ],
        quality_issues=[
            DatasetQualityIssue(
                dataset_id=dataset_id,
                rule=issue.rule,
                column_name=issue.column_name,
                severity=issue.severity,
                message=issue.message,
                score_impact=issue.score_impact,
            )
            for issue in issues
        ],
        lineage_events=events,
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def list_datasets(db: Session, limit: int = 50, offset: int = 0) -> list[Dataset]:
    stmt = select(Dataset).order_by(Dataset.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


def get_dataset(db: Session, dataset_id: uuid.UUID) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise DatasetNotFoundError(f"Dataset {dataset_id} not found.")
    return dataset


def get_preview(
    db: Session, dataset_id: uuid.UUID, limit: int = DEFAULT_PREVIEW_LIMIT
) -> tuple[list[str], list[dict]]:
    dataset = get_dataset(db, dataset_id)
    ordered_columns = sorted(dataset.columns, key=lambda c: c.position)
    columns = {c.column_name: c.detected_type for c in ordered_columns}

    table = build_dataset_table(dataset.storage_table_name, columns)
    rows = fetch_preview_rows(db.connection(), table, limit)
    clean_rows = [{k: v for k, v in row.items() if k != "_row_id"} for row in rows]
    return list(columns.keys()), clean_rows


def delete_dataset(db: Session, dataset_id: uuid.UUID) -> None:
    dataset = get_dataset(db, dataset_id)
    drop_dataset_table(db.connection(), dataset.storage_table_name)
    db.delete(dataset)
    db.commit()
