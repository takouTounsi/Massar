from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool = True
    is_verified: bool = True
    two_factor_enabled: bool = False
    created_at: datetime
    updated_at: datetime


class UserRecord(UserPublic):
    password_hash: str
    two_factor_secret: str | None = None
    pending_two_factor_secret: str | None = None


class RegisterRequest(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    requires_2fa: bool = False
    temporary_login_token: str | None = None
    user: UserPublic | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetResponse(BaseModel):
    reset_token: str
    message: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=10, max_length=128)


class TwoFactorSetupResponse(BaseModel):
    otpauth_uri: str
    secret: str
    manual_entry_key: str


class TwoFactorCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class TwoFactorVerifyRequest(TwoFactorCodeRequest):
    temporary_login_token: str


class MessageResponse(BaseModel):
    message: str
