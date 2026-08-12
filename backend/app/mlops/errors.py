"""Exceptions raised by the MLOps package."""


class MlOpsError(Exception):
    """Base class for all MLOps failures."""


class ModelVersionNotFoundError(MlOpsError):
    """Raised when a model version id doesn't exist."""


class AlreadyRegisteredError(MlOpsError):
    """Raised when an MLRun has already been registered as a model version."""


class InvalidLifecycleTransitionError(MlOpsError):
    """Raised when a requested promote/archive transition isn't allowed from
    the version's current status - always carries a specific reason."""


class MonitoringEventNotFoundError(MlOpsError):
    """Raised when a monitoring event id doesn't exist."""


class InsufficientDataForMonitoringError(MlOpsError):
    """Raised when the dataset supplied for a drift/performance check is
    missing a column the check genuinely needs (e.g. no target column for a
    classification performance check)."""
