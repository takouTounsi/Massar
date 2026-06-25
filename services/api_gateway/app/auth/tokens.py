from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    type: str
    exp: int
    jti: str
    extra: dict[str, Any]


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(
    *,
    subject: str,
    token_type: str,
    secret_key: str,
    expires_in_seconds: int,
    extra: dict[str, Any] | None = None,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "type": token_type,
        "exp": int(time.time()) + expires_in_seconds,
        "iat": int(time.time()),
        "jti": str(uuid4()),
        **(extra or {}),
    }
    signing_input = ".".join(
        [
            _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(secret_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def decode_token(token: str, *, secret_key: str, expected_type: str | None = None) -> TokenPayload:
    try:
        header_raw, payload_raw, signature_raw = token.split(".", 2)
    except ValueError as exc:
        raise TokenError("Malformed token") from exc
    signing_input = f"{header_raw}.{payload_raw}"
    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(_b64encode(expected_signature), signature_raw):
        raise TokenError("Invalid token signature")
    payload = json.loads(_b64decode(payload_raw))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise TokenError("Token expired")
    token_type = str(payload.get("type", ""))
    if expected_type is not None and token_type != expected_type:
        raise TokenError("Unexpected token type")
    extra = {
        key: value
        for key, value in payload.items()
        if key not in {"sub", "type", "exp", "iat", "jti"}
    }
    return TokenPayload(
        sub=str(payload["sub"]),
        type=token_type,
        exp=int(payload["exp"]),
        jti=str(payload["jti"]),
        extra=extra,
    )
