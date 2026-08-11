"""Exceptions raised by the ML pipeline."""


class MlError(Exception):
    """Base class for all ML pipeline failures."""


class DatasetNotSuitableError(MlError):
    """Raised when a dataset fails a task's suitability check.

    Always carries a human-readable, specific reason (e.g. "no datetime
    column was detected") - never a generic "invalid dataset."
    """


class InvalidMlConfigurationError(MlError):
    """Raised for a structurally invalid request: an unknown column name,
    an out-of-range parameter, a target with the wrong number of classes."""


class MlRunNotFoundError(MlError):
    """Raised when a run id doesn't exist."""


class ArtifactNotFoundError(MlError):
    """Raised when a run's persisted model artifact is missing or unreadable."""
