"""Pydantic request/response models for the auth API.

UserOut never includes password_hash - it isn't even a field on the model,
so there's nothing to accidentally serialize.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    roles: list[str]
    permissions: list[str]
