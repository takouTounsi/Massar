from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response

from services.api_gateway.app.auth.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TwoFactorCodeRequest,
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
    UserPublic,
)
from services.api_gateway.app.auth.service import auth_service
from services.api_gateway.app.dependencies import require_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
REFRESH_COOKIE = "massar_refresh_token"


def _set_refresh_cookie(response: Response, auth_response: AuthResponse) -> None:
    if not auth_response.refresh_token:
        return
    response.set_cookie(
        REFRESH_COOKIE,
        auth_response.refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


@router.post("/register", response_model=UserPublic)
async def register(payload: RegisterRequest) -> UserPublic:
    return auth_service.register(payload)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, response: Response) -> AuthResponse:
    auth_response = auth_service.login(payload.email, payload.password)
    _set_refresh_cookie(response, auth_response)
    return auth_response


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> MessageResponse:
    auth_service.logout(refresh_token)
    response.delete_cookie(REFRESH_COOKIE, path="/")
    return MessageResponse(message="Logged out")


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    payload: RefreshRequest,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> AuthResponse:
    token = payload.refresh_token or refresh_token
    if token is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    auth_response = auth_service.refresh(token)
    _set_refresh_cookie(response, auth_response)
    return auth_response


@router.get("/me", response_model=UserPublic)
async def me(current_user: UserPublic = Depends(require_user)) -> UserPublic:
    return current_user


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: UserPublic = Depends(require_user),
) -> MessageResponse:
    auth_service.change_password(current_user.id, payload.current_password, payload.new_password)
    return MessageResponse(message="Password updated")


@router.post("/request-password-reset", response_model=PasswordResetResponse)
async def request_password_reset(payload: PasswordResetRequest) -> PasswordResetResponse:
    token = auth_service.request_password_reset(payload.email)
    return PasswordResetResponse(
        reset_token=token,
        message="Demo reset token generated. In production this would be emailed.",
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest) -> MessageResponse:
    auth_service.reset_password(payload.reset_token, payload.new_password)
    return MessageResponse(message="Password reset complete")


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(current_user: UserPublic = Depends(require_user)) -> TwoFactorSetupResponse:
    secret, uri = auth_service.setup_2fa(current_user.id)
    return TwoFactorSetupResponse(otpauth_uri=uri, secret=secret, manual_entry_key=secret)


@router.post("/2fa/confirm", response_model=UserPublic)
async def confirm_2fa(
    payload: TwoFactorCodeRequest,
    current_user: UserPublic = Depends(require_user),
) -> UserPublic:
    return auth_service.confirm_2fa(current_user.id, payload.code)


@router.post("/2fa/verify", response_model=AuthResponse)
async def verify_2fa(payload: TwoFactorVerifyRequest, response: Response) -> AuthResponse:
    auth_response = auth_service.verify_2fa_login(payload.temporary_login_token, payload.code)
    _set_refresh_cookie(response, auth_response)
    return auth_response


@router.post("/2fa/disable", response_model=UserPublic)
async def disable_2fa(
    payload: TwoFactorCodeRequest,
    current_user: UserPublic = Depends(require_user),
) -> UserPublic:
    return auth_service.disable_2fa(current_user.id, payload.code)
