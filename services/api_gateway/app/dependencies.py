from fastapi import Depends, Header, HTTPException, status

from shared.config import Settings, get_settings

from services.api_gateway.app.auth.schemas import UserPublic
from services.api_gateway.app.auth.service import auth_service


def settings_dependency() -> Settings:
    return get_settings()


def require_user(authorization: str | None = Header(default=None)) -> UserPublic:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    token = authorization.split(" ", 1)[1].strip()
    return auth_service.get_current_user(token)
