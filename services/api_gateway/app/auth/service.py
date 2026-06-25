from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from shared.config import Settings, get_settings

from services.api_gateway.app.auth.schemas import (
    AuthResponse,
    RegisterRequest,
    UserPublic,
    UserRecord,
)
from services.api_gateway.app.auth.security import (
    hash_password,
    normalize_email,
    validate_email,
    validate_password_policy,
    verify_password,
)
from services.api_gateway.app.auth.tokens import TokenError, create_token, decode_token
from services.api_gateway.app.auth.two_factor import (
    build_otpauth_uri,
    generate_totp_secret,
    verify_totp_code,
)


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "demo_users.json"
DEMO_PASSWORD = "MassarDemo123!"


class AuthService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.users_by_email: dict[str, UserRecord] = {}
        self.users_by_id: dict[str, UserRecord] = {}
        self.revoked_refresh_jtis: set[str] = set()
        self.reset_tokens: dict[str, str] = {}
        self.failed_login_attempts: dict[str, list[float]] = {}
        self._load_demo_users()

    def _load_demo_users(self) -> None:
        if not DATA_FILE.exists():
            return
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for item in data.get("users", []):
            payload = dict(item)
            if not payload.get("password_hash"):
                payload["password_hash"] = hash_password(DEMO_PASSWORD)
            record = UserRecord.model_validate(payload)
            self._store_user(record)

    def _store_user(self, user: UserRecord) -> None:
        self.users_by_email[normalize_email(user.email)] = user
        self.users_by_id[str(user.id)] = user

    def _public(self, user: UserRecord) -> UserPublic:
        return UserPublic(**user.model_dump(exclude={"password_hash", "two_factor_secret", "pending_two_factor_secret"}))

    def register(self, payload: RegisterRequest) -> UserPublic:
        email = normalize_email(payload.email)
        try:
            validate_email(email)
            validate_password_policy(payload.password)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        if email in self.users_by_email:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        now = datetime.now(UTC)
        record = UserRecord(
            id=uuid4(),
            email=email,
            full_name=payload.full_name.strip(),
            password_hash=hash_password(payload.password),
            is_active=True,
            is_verified=True,
            two_factor_enabled=False,
            created_at=now,
            updated_at=now,
        )
        self._store_user(record)
        return self._public(record)

    def login(self, email: str, password: str) -> AuthResponse:
        email = normalize_email(email)
        self._enforce_login_rate_limit(email)
        user = self.users_by_email.get(email)
        if user is None or not verify_password(password, user.password_hash):
            self._record_login_failure(email)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
        self.failed_login_attempts.pop(email, None)
        if user.two_factor_enabled:
            return AuthResponse(
                requires_2fa=True,
                temporary_login_token=self._create_temp_login_token(user),
                user=self._public(user),
            )
        return self.create_session(user)

    def create_session(self, user: UserRecord) -> AuthResponse:
        access_ttl = self.settings.jwt_access_token_expire_minutes * 60
        refresh_ttl = self.settings.jwt_refresh_token_expire_days * 24 * 60 * 60
        return AuthResponse(
            access_token=create_token(
                subject=str(user.id),
                token_type="access",
                secret_key=self.settings.jwt_secret_key,
                expires_in_seconds=access_ttl,
            ),
            refresh_token=create_token(
                subject=str(user.id),
                token_type="refresh",
                secret_key=self.settings.jwt_secret_key,
                expires_in_seconds=refresh_ttl,
            ),
            expires_in=access_ttl,
            user=self._public(user),
        )

    def refresh(self, refresh_token: str) -> AuthResponse:
        payload = self.decode_refresh(refresh_token)
        user = self.get_user_by_id(payload.sub)
        return self.create_session(user)

    def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        try:
            payload = decode_token(
                refresh_token,
                secret_key=self.settings.jwt_secret_key,
                expected_type="refresh",
            )
        except TokenError:
            return
        self.revoked_refresh_jtis.add(payload.jti)

    def get_user_by_id(self, user_id: str) -> UserRecord:
        user = self.users_by_id.get(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
        return user

    def get_current_user(self, access_token: str) -> UserPublic:
        try:
            payload = decode_token(
                access_token,
                secret_key=self.settings.jwt_secret_key,
                expected_type="access",
            )
        except TokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        return self._public(self.get_user_by_id(payload.sub))

    def change_password(self, user_id: UUID, current_password: str, new_password: str) -> None:
        user = self.get_user_by_id(str(user_id))
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is invalid")
        try:
            validate_password_policy(new_password)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(UTC)

    def request_password_reset(self, email: str) -> str:
        normalized = normalize_email(email)
        token = create_token(
            subject=normalized,
            token_type="password_reset",
            secret_key=self.settings.jwt_secret_key,
            expires_in_seconds=20 * 60,
        )
        self.reset_tokens[token] = normalized
        return token

    def reset_password(self, reset_token: str, new_password: str) -> None:
        email = self.reset_tokens.pop(reset_token, None)
        if email is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")
        try:
            decode_token(reset_token, secret_key=self.settings.jwt_secret_key, expected_type="password_reset")
            validate_password_policy(new_password)
        except (TokenError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        user = self.users_by_email.get(email)
        if user is not None:
            user.password_hash = hash_password(new_password)
            user.updated_at = datetime.now(UTC)

    def setup_2fa(self, user_id: UUID) -> tuple[str, str]:
        if not self.settings.enable_2fa:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="2FA is disabled")
        user = self.get_user_by_id(str(user_id))
        secret = generate_totp_secret()
        user.pending_two_factor_secret = secret
        user.updated_at = datetime.now(UTC)
        return secret, build_otpauth_uri(email=user.email, secret=secret)

    def confirm_2fa(self, user_id: UUID, code: str) -> UserPublic:
        user = self.get_user_by_id(str(user_id))
        secret = user.pending_two_factor_secret
        if not secret or not verify_totp_code(secret, code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 2FA code")
        user.two_factor_secret = secret
        user.pending_two_factor_secret = None
        user.two_factor_enabled = True
        user.updated_at = datetime.now(UTC)
        return self._public(user)

    def verify_2fa_login(self, temporary_login_token: str, code: str) -> AuthResponse:
        try:
            payload = decode_token(
                temporary_login_token,
                secret_key=self.settings.jwt_secret_key,
                expected_type="2fa",
            )
        except TokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        user = self.get_user_by_id(payload.sub)
        if not user.two_factor_secret or not verify_totp_code(user.two_factor_secret, code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA code")
        return self.create_session(user)

    def disable_2fa(self, user_id: UUID, code: str) -> UserPublic:
        user = self.get_user_by_id(str(user_id))
        if user.two_factor_secret and not verify_totp_code(user.two_factor_secret, code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 2FA code")
        user.two_factor_secret = None
        user.pending_two_factor_secret = None
        user.two_factor_enabled = False
        user.updated_at = datetime.now(UTC)
        return self._public(user)

    def decode_refresh(self, refresh_token: str):
        try:
            payload = decode_token(
                refresh_token,
                secret_key=self.settings.jwt_secret_key,
                expected_type="refresh",
            )
        except TokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        if payload.jti in self.revoked_refresh_jtis:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
        return payload

    def _create_temp_login_token(self, user: UserRecord) -> str:
        return create_token(
            subject=str(user.id),
            token_type="2fa",
            secret_key=self.settings.jwt_secret_key,
            expires_in_seconds=5 * 60,
        )

    def _enforce_login_rate_limit(self, email: str) -> None:
        now = time.time()
        attempts = [item for item in self.failed_login_attempts.get(email, []) if now - item < 60]
        self.failed_login_attempts[email] = attempts
        if len(attempts) >= 5:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")

    def _record_login_failure(self, email: str) -> None:
        self.failed_login_attempts.setdefault(email, []).append(time.time())


auth_service = AuthService()
