"""Pydantic request/response models for role/permission/user-admin APIs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RoleOut(BaseModel):
    id: int
    name: str
    description: str | None


class PermissionOut(BaseModel):
    id: int
    name: str
    description: str | None


class UserAdminOut(BaseModel):
    """A user as seen by an admin in the user-management UI."""

    id: UUID
    email: str
    full_name: str
    is_active: bool
    roles: list[str]
    created_at: datetime
    updated_at: datetime


class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class AssignRolesRequest(BaseModel):
    role_names: list[str] = Field(min_length=1)
