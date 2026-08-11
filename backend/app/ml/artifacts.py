"""Joblib persistence for trained ML pipelines/models.

One file per run, named by run id, under Settings.ml_artifacts_dir -
gitignored, never committed, same pattern as Settings.upload_storage_dir
for retained raw uploads. This is deliberately NOT a model registry
(no versioning across runs of "the same" model, no promotion workflow) -
that's Phase 6 (MLOps). Each run's artifact is independent and immutable.
"""

import uuid
from pathlib import Path
from typing import Any

import joblib

from app.ml.errors import ArtifactNotFoundError


def artifact_path(artifacts_dir: Path, run_id: uuid.UUID) -> Path:
    return artifacts_dir / f"{run_id}.joblib"


def save_artifact(artifacts_dir: Path, run_id: uuid.UUID, artifact: Any) -> Path:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_path(artifacts_dir, run_id)
    joblib.dump(artifact, path)
    return path


def load_artifact(artifacts_dir: Path, run_id: uuid.UUID) -> Any:
    path = artifact_path(artifacts_dir, run_id)
    if not path.exists():
        raise ArtifactNotFoundError(f"No stored model artifact for run {run_id}.")
    return joblib.load(path)
