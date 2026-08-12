"""Model version lifecycle: register, list, get, promote, archive.

State machine (deliberately simple - see app/models/model_version.py's
module docstring for "why not a richer one"):

    candidate --promote--> staging --promote--> production
       ^                      |                      |
       |                      +------archive---------+
       +------------------------archive---------------

`archive` is terminal here: an archived version can't be un-archived or
promoted directly. This is a deliberate simplification for this project's
scale - the "correct" way back into rotation is registering a *new* version
(e.g. retraining), not resurrecting an old one, which keeps the state
machine's edges few enough to reason about completely. Promotion always
moves exactly one stage forward; jumping candidate -> production directly
is rejected (a version must pass through staging first) - both are checked
in `_ALLOWED_PROMOTIONS` and `archive`'s status check below, not scattered
across the API layer.
"""

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.artifacts import artifact_path
from app.ml.errors import ArtifactNotFoundError
from app.mlops.errors import (
    AlreadyRegisteredError,
    InvalidLifecycleTransitionError,
    ModelVersionNotFoundError,
)
from app.models.ml_run import MLRun
from app.models.model_version import ModelVersion

# candidate -> staging -> production: the only forward transitions allowed.
_ALLOWED_PROMOTIONS: dict[str, str] = {"candidate": "staging", "staging": "production"}
_ARCHIVABLE_STATUSES = {"candidate", "staging", "production"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _sha256_of_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_version(
    db: Session, settings, run: MLRun, created_by: uuid.UUID | None
) -> ModelVersion:
    """Registers a completed MLRun as a new candidate model version.

    Raises AlreadyRegisteredError if this run already has a version (one
    version per run - re-registering the same run is never meaningful).
    Raises ArtifactNotFoundError if the run's artifact file is missing on
    disk (can't compute a checksum for something that doesn't exist).
    """
    existing = db.execute(
        select(ModelVersion).where(ModelVersion.ml_run_id == run.id)
    ).scalar_one_or_none()
    if existing is not None:
        raise AlreadyRegisteredError(
            f"MLRun {run.id} is already registered as model version {existing.id}."
        )

    path = artifact_path(settings.ml_artifacts_dir, run.id)
    if not path.exists():
        raise ArtifactNotFoundError(
            f"No stored model artifact for run {run.id} - cannot register it."
        )
    checksum = _sha256_of_file(path)

    max_version = db.execute(
        select(ModelVersion.version_number)
        .where(ModelVersion.dataset_id == run.dataset_id, ModelVersion.task_type == run.task_type)
        .order_by(ModelVersion.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_version = (max_version or 0) + 1

    version = ModelVersion(
        ml_run_id=run.id,
        dataset_id=run.dataset_id,
        task_type=run.task_type,
        model_name=run.model_name,
        version_number=next_version,
        status="candidate",
        artifact_checksum=checksum,
        created_by=created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def get_version(db: Session, version_id: uuid.UUID) -> ModelVersion:
    version = db.get(ModelVersion, version_id)
    if version is None:
        raise ModelVersionNotFoundError(f"Model version {version_id} not found.")
    return version


def list_versions(
    db: Session, *, dataset_id: uuid.UUID | None = None, task_type: str | None = None,
    status: str | None = None, limit: int = 100,
) -> list[ModelVersion]:
    stmt = select(ModelVersion).order_by(ModelVersion.created_at.desc()).limit(limit)
    if dataset_id is not None:
        stmt = stmt.where(ModelVersion.dataset_id == dataset_id)
    if task_type is not None:
        stmt = stmt.where(ModelVersion.task_type == task_type)
    if status is not None:
        stmt = stmt.where(ModelVersion.status == status)
    return list(db.execute(stmt).scalars())


def get_production_version(
    db: Session, dataset_id: uuid.UUID, task_type: str
) -> ModelVersion | None:
    return db.execute(
        select(ModelVersion).where(
            ModelVersion.dataset_id == dataset_id, ModelVersion.task_type == task_type,
            ModelVersion.status == "production",
        )
    ).scalar_one_or_none()


def promote_version(
    db: Session, version_id: uuid.UUID, target_status: str, promoted_by: uuid.UUID | None,
    ml_run: MLRun,
) -> tuple[ModelVersion, ModelVersion | None]:
    """Promotes a version one stage forward. Returns (promoted_version,
    auto_archived_previous_production_version_or_None).

    A version's linked MLRun must have status "completed" (always true
    today since training is synchronous - see MLRun.status's docstring -
    but checked explicitly so this stays correct if Phase 7+ ever makes
    training asynchronous)."""
    version = get_version(db, version_id)
    if ml_run.status != "completed":
        raise InvalidLifecycleTransitionError(
            f"Cannot promote model version {version_id}: its training run has status "
            f"'{ml_run.status}', not 'completed'."
        )

    expected_next = _ALLOWED_PROMOTIONS.get(version.status)
    if expected_next != target_status:
        raise InvalidLifecycleTransitionError(
            f"Cannot promote model version {version_id} from '{version.status}' to "
            f"'{target_status}' - allowed promotions are "
            f"{', '.join(f'{k}->{v}' for k, v in _ALLOWED_PROMOTIONS.items())}."
        )

    auto_archived = None
    if target_status == "production":
        current_production = get_production_version(db, version.dataset_id, version.task_type)
        if current_production is not None and current_production.id != version.id:
            # Archived and committed *before* the new version is set to
            # production, in its own statement/transaction - the partial
            # unique index on (dataset_id, task_type) WHERE status =
            # 'production' isn't (can't be, in Postgres - a partial unique
            # index has no DEFERRABLE option) deferred to commit time, so
            # doing both updates in one flush risks the DB briefly seeing
            # two "production" rows mid-batch depending on statement
            # ordering, which the constraint would then legitimately reject.
            current_production.status = "archived"
            current_production.promoted_by = promoted_by
            current_production.promoted_at = _utcnow()
            db.commit()
            auto_archived = current_production

    version.status = target_status
    version.promoted_by = promoted_by
    version.promoted_at = _utcnow()
    db.commit()
    db.refresh(version)
    if auto_archived is not None:
        db.refresh(auto_archived)
    return version, auto_archived


def archive_version(
    db: Session, version_id: uuid.UUID, archived_by: uuid.UUID | None
) -> ModelVersion:
    version = get_version(db, version_id)
    if version.status not in _ARCHIVABLE_STATUSES:
        raise InvalidLifecycleTransitionError(
            f"Model version {version_id} is already '{version.status}' - nothing to archive."
        )
    version.status = "archived"
    version.promoted_by = archived_by
    version.promoted_at = _utcnow()
    db.commit()
    db.refresh(version)
    return version
