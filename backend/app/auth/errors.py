"""Exceptions raised by the auth module."""


class AuthError(Exception):
    """Base class for all authentication failures."""


class EmailAlreadyRegisteredError(AuthError):
    """Raised on registration with an email that's already in use."""


class InvalidCredentialsError(AuthError):
    """Wrong email or password.

    Deliberately the *same* exception (and message) for "no such email"
    and "wrong password" - distinguishing them would let a caller enumerate
    which emails are registered.
    """


class InactiveUserError(AuthError):
    """Credentials were correct, but the account has been deactivated."""


class InvalidTokenError(AuthError):
    """The JWT is malformed, has an invalid signature, has expired, or its
    token_version no longer matches the user's current one."""
