"""Classical ML API (Phase 5): suitability, training, run history, predictions.

Thin HTTP layer only - all computation lives in app/ml/service.py. Three
permissions gate this router (see app/rbac/seed.py): `ml:read` (suitability,
run history, results), `ml:train` (kick off a new training run), and
`ml:predict` (score new predictions from an already-trained run).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record_event
from app.config import Settings, get_settings
from app.db import get_db
from app.ingestion.errors import DatasetNotFoundError
from app.ml import service
from app.ml.errors import ArtifactNotFoundError, InvalidMlConfigurationError, MlRunNotFoundError
from app.ml.schemas import (
    AnomalyTrainRequest,
    ClassificationTrainRequest,
    DatasetSuitabilityOut,
    ForecastTrainRequest,
    MLRunOut,
    MLRunResultsOut,
    PredictionResponseOut,
    PredictRequest,
    SegmentationTrainRequest,
)
from app.models.ml_run import MLRun
from app.models.user import User
from app.rbac.dependencies import require_permission

router = APIRouter(tags=["ml"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_run_out(run: MLRun) -> MLRunOut:
    return MLRunOut.model_validate(run, from_attributes=True)


def _to_results_out(run: MLRun) -> MLRunResultsOut:
    return MLRunResultsOut(run=_to_run_out(run), results=run.results)


def _record_training(request: Request, db: Session, current_user: User, run: MLRun) -> None:
    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.ML_MODEL_TRAINED,
        resource_type="ml_run",
        resource_id=str(run.id),
        metadata={
            "dataset_id": str(run.dataset_id),
            "task_type": run.task_type,
            "model_name": run.model_name,
        },
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()


# ---------------------------------------------------------------------------
# Suitability
# ---------------------------------------------------------------------------


@router.get("/datasets/{dataset_id}/ml/suitability", response_model=DatasetSuitabilityOut)
def get_suitability(
    dataset_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("ml:read")),
) -> DatasetSuitabilityOut:
    try:
        return service.get_dataset_suitability(db, dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------


@router.post("/ml/train/classification", response_model=MLRunResultsOut, status_code=201)
def train_classification(
    request: Request,
    body: ClassificationTrainRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("ml:train")),
) -> MLRunResultsOut:
    try:
        run = service.train_classification_run(db, settings, body, current_user.id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidMlConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record_training(request, db, current_user, run)
    return _to_results_out(run)


@router.post("/ml/train/forecasting", response_model=MLRunResultsOut, status_code=201)
def train_forecasting(
    request: Request,
    body: ForecastTrainRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("ml:train")),
) -> MLRunResultsOut:
    try:
        run = service.train_forecast_run(db, settings, body, current_user.id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidMlConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record_training(request, db, current_user, run)
    return _to_results_out(run)


@router.post("/ml/train/segmentation", response_model=MLRunResultsOut, status_code=201)
def train_segmentation(
    request: Request,
    body: SegmentationTrainRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("ml:train")),
) -> MLRunResultsOut:
    try:
        run = service.train_segmentation_run(db, settings, body, current_user.id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidMlConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record_training(request, db, current_user, run)
    return _to_results_out(run)


@router.post("/ml/train/anomaly-detection", response_model=MLRunResultsOut, status_code=201)
def train_anomaly_detection(
    request: Request,
    body: AnomalyTrainRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_permission("ml:train")),
) -> MLRunResultsOut:
    try:
        run = service.train_anomaly_run(db, settings, body, current_user.id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidMlConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record_training(request, db, current_user, run)
    return _to_results_out(run)


# ---------------------------------------------------------------------------
# Run history + results
# ---------------------------------------------------------------------------


@router.get("/ml/runs", response_model=list[MLRunOut])
def list_runs(
    dataset_id: UUID | None = None,
    task_type: str | None = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("ml:read")),
) -> list[MLRunOut]:
    runs = service.list_runs(db, dataset_id=dataset_id, task_type=task_type)
    return [_to_run_out(run) for run in runs]


@router.get("/ml/runs/{run_id}", response_model=MLRunResultsOut)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("ml:read")),
) -> MLRunResultsOut:
    try:
        run = service.get_run(db, run_id)
    except MlRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_results_out(run)


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------


@router.post("/ml/runs/{run_id}/predict", response_model=PredictionResponseOut)
def predict(
    run_id: UUID,
    body: PredictRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _current_user: User = Depends(require_permission("ml:predict")),
) -> PredictionResponseOut:
    try:
        return service.predict_run(db, settings, run_id, body.horizon)
    except MlRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
