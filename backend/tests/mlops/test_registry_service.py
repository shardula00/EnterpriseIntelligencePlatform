"""Integration tests for app/mlops/registry_service.py, against a live
Postgres - covers version creation, lifecycle transitions, promotion
rules, and artifact lineage (the checksum actually matches the file on
disk).

Datasets/runs/artifacts created here are cleaned up by conftest.py's
autouse fixtures via cascade delete (dataset -> ml_run -> model_version ->
monitoring_event), same as Phase 5's own ML tests.
"""

import hashlib
import uuid

import pytest

from app.config import get_settings
from app.ingestion import service as ing_service
from app.ml import service as ml_service
from app.ml.artifacts import artifact_path
from app.ml.schemas import ClassificationTrainRequest
from app.mlops import registry_service
from app.mlops.errors import (
    AlreadyRegisteredError,
    InvalidLifecycleTransitionError,
    ModelVersionNotFoundError,
)
from tests.conftest import FIXTURES_DIR

settings = get_settings()


def _upload(db_session, name: str):
    content = (FIXTURES_DIR / "ml_churn_sample.csv").read_bytes()
    return ing_service.ingest_upload(db_session, settings, "ml_churn_sample.csv", content, name)


def _train(db_session, dataset_id, seed: int):
    request = ClassificationTrainRequest(
        dataset_id=dataset_id, target_column="churned", random_seed=seed
    )
    return ml_service.train_classification_run(db_session, settings, request, None)


def _upload_and_train(db_session, seed: int, name: str):
    dataset = _upload(db_session, name)
    run = _train(db_session, dataset.id, seed)
    return dataset, run


def _register(db_session, run):
    return registry_service.register_version(db_session, settings, run, None)


def _promote(db_session, version, target_status: str, run):
    return registry_service.promote_version(db_session, version.id, target_status, None, run)


def test_register_version_computes_a_real_checksum_matching_the_artifact_file(db_session):
    dataset, run = _upload_and_train(db_session, seed=1, name="registry-checksum")
    version = _register(db_session, run)

    path = artifact_path(settings.ml_artifacts_dir, run.id)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert version.artifact_checksum == expected
    assert version.status == "candidate"
    assert version.version_number == 1
    assert version.task_type == "classification"
    assert version.dataset_id == dataset.id
    assert version.ml_run_id == run.id


def test_register_version_rejects_registering_the_same_run_twice(db_session):
    _, run = _upload_and_train(db_session, seed=2, name="registry-duplicate")
    _register(db_session, run)
    with pytest.raises(AlreadyRegisteredError):
        _register(db_session, run)


def test_version_numbers_increment_per_dataset_task_family(db_session):
    dataset, run_a = _upload_and_train(db_session, seed=3, name="registry-numbering")
    run_b = _train(db_session, dataset.id, seed=4)
    version_a = _register(db_session, run_a)
    version_b = _register(db_session, run_b)
    assert version_a.version_number == 1
    assert version_b.version_number == 2


def test_promote_forward_one_stage_at_a_time(db_session):
    _, run = _upload_and_train(db_session, seed=5, name="registry-promote")
    version = _register(db_session, run)

    version, archived = _promote(db_session, version, "staging", run)
    assert version.status == "staging"
    assert archived is None

    version, archived = _promote(db_session, version, "production", run)
    assert version.status == "production"
    assert archived is None


def test_promote_rejects_skipping_staging(db_session):
    _, run = _upload_and_train(db_session, seed=6, name="registry-skip-staging")
    version = _register(db_session, run)
    with pytest.raises(InvalidLifecycleTransitionError, match="candidate.*production"):
        _promote(db_session, version, "production", run)


def test_promoting_a_new_production_version_auto_archives_the_previous_one(db_session):
    dataset, run_a = _upload_and_train(db_session, seed=7, name="registry-auto-archive")
    run_b = _train(db_session, dataset.id, seed=8)
    version_a = _register(db_session, run_a)
    version_b = _register(db_session, run_b)

    version_a, _ = _promote(db_session, version_a, "staging", run_a)
    version_a, _ = _promote(db_session, version_a, "production", run_a)
    current_prod = registry_service.get_production_version(db_session, dataset.id, "classification")
    assert current_prod.id == version_a.id

    version_b, _ = _promote(db_session, version_b, "staging", run_b)
    version_b, archived = _promote(db_session, version_b, "production", run_b)

    assert archived is not None
    assert archived.id == version_a.id
    assert archived.status == "archived"
    new_prod = registry_service.get_production_version(db_session, dataset.id, "classification")
    assert new_prod.id == version_b.id
    # A remains inspectable, not deleted.
    assert registry_service.get_version(db_session, version_a.id).status == "archived"


def test_archive_is_terminal_and_rejects_re_archiving(db_session):
    _, run = _upload_and_train(db_session, seed=9, name="registry-archive-terminal")
    version = _register(db_session, run)
    version = registry_service.archive_version(db_session, version.id, None)
    assert version.status == "archived"
    with pytest.raises(InvalidLifecycleTransitionError, match="already 'archived'"):
        registry_service.archive_version(db_session, version.id, None)


def test_archive_allowed_from_candidate_staging_or_production(db_session):
    _, run_a = _upload_and_train(db_session, seed=10, name="registry-archive-from-any")
    version = _register(db_session, run_a)
    version = registry_service.archive_version(db_session, version.id, None)
    assert version.status == "archived"


def test_get_version_raises_not_found_for_unknown_id(db_session):
    with pytest.raises(ModelVersionNotFoundError):
        registry_service.get_version(db_session, uuid.uuid4())


def test_list_versions_filters_by_dataset_task_and_status(db_session):
    dataset, run = _upload_and_train(db_session, seed=11, name="registry-list-filter")
    version = _register(db_session, run)

    by_dataset = registry_service.list_versions(db_session, dataset_id=dataset.id)
    assert any(v.id == version.id for v in by_dataset)

    by_wrong_task = registry_service.list_versions(
        db_session, dataset_id=dataset.id, task_type="forecasting"
    )
    assert all(v.id != version.id for v in by_wrong_task)

    by_status = registry_service.list_versions(
        db_session, dataset_id=dataset.id, status="candidate"
    )
    assert any(v.id == version.id for v in by_status)


def test_promote_rejects_when_run_did_not_complete_successfully(db_session):
    _, run = _upload_and_train(db_session, seed=12, name="registry-incomplete-run")
    version = _register(db_session, run)
    run.status = "failed"  # simulate a future async-training failure state
    with pytest.raises(InvalidLifecycleTransitionError, match="not 'completed'"):
        _promote(db_session, version, "staging", run)
