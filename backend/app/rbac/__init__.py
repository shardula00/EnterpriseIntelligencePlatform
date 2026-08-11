"""Authorization: roles, permissions, and role assignment.

Deliberately separate from app/auth/ (identity). A user's *identity* comes
from a verified token; what that identity is *allowed to do* is resolved
fresh from the database on every request via effective_permissions() -
never cached in the token.
"""
