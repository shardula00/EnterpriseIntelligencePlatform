"""Exceptions raised by the rbac module."""


class RbacError(Exception):
    """Base class for all authorization failures."""


class RoleNotFoundError(RbacError):
    """Raised when an unknown role name is referenced (e.g. role assignment)."""


class UserNotFoundError(RbacError):
    """Raised when an admin operation targets a user id that doesn't exist."""


class SelfModificationError(RbacError):
    """Raised when a user tries to change their own role assignment or
    active status - the specific mechanism this app uses to prevent
    self-privilege-escalation (see app/rbac/service.py)."""
