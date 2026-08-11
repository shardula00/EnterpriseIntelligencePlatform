"""Classical machine learning over generic ingested datasets (Phase 5).

Nothing here is specific to one business schema - a "target column" or
"feature column" is always something the caller names from a dataset's
*actual* detected columns (see app/models/dataset.py's DatasetColumn),
never a hardcoded name. Training reuses the same physical tables Phase 2
already created (see data_loading.py) - there is no second ingestion path.

Module map:
  errors.py               - exceptions
  schemas.py              - Pydantic request/response models
  data_loading.py          - load a dataset's full table into a DataFrame
  suitability.py            - per-task suitability checks + column suggestions
  feature_engineering.py     - reusable preprocessing (fit on train only - see
                              its docstring for the leakage-prevention rule)
  evaluation.py                - shared metric/seed helpers
  explainability.py             - feature importance (native + permutation)
  classification.py, forecasting.py, segmentation.py, anomaly_detection.py
                                 - one train/evaluate function per task
  artifacts.py                   - joblib persistence for trained pipelines
  service.py                      - orchestration; the only module the API
                                    layer (app/api/ml.py) calls directly
"""
