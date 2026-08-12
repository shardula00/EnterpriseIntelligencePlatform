"""MLOps hardening (Phase 6): model registry, drift detection, performance
monitoring, and alerting - built on top of Phase 5's `app/ml/` rather than
inside it. The phase boundary is deliberate: `app/ml/` answers "can I train
and evaluate a model correctly," this package answers "can I trust that
model over time, and manage more than one version of it."

Module map:
    errors.py            - exception hierarchy
    schemas.py           - Pydantic request/response contracts
    registry_service.py  - model version lifecycle (register/promote/archive)
    drift.py             - data drift detection (PSI-based)
    monitoring.py        - per-task performance-degradation checks
    service.py            - the only module app/api/mlops.py calls; wires
                            the above together with MonitoringEvent
                            persistence and MLRun/dataset lookups

Deliberately NOT implemented (see DEVELOPMENT_PLAN.md's Phase 6 section):
    - MLflow. A lightweight native registry (ModelVersion + MonitoringEvent
      tables) is enough at this project's scale - one more heavyweight
      dependency wasn't justified when the actual need is "track a status
      enum and a metrics comparison," not a full experiment-tracking UI.
    - Celery/Redis/async job execution. Drift/monitoring checks run over
      the same row counts Phase 5's training does (documented there as
      fine synchronously); revisit together if that changes.
    - Automatic retraining/remediation. Detection and remediation are
      deliberately kept separate - this package only ever reports a status,
      never retrains or unpromotes a model on its own.
    - External alerting (email/Slack/etc). MonitoringEvent's normalized
      `severity` field exists so a future notifier can be added by reading
      that table, without touching the detection engine - see
      app/models/monitoring_event.py.
"""
