from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
from urllib.parse import quote


def generate_totp_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def build_otpauth_uri(*, email: str, secret: str, issuer: str = "Massar") -> str:
    label = quote(f"{issuer}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def generate_totp_code(secret: str, *, for_time: int | None = None, period: int = 30) -> str:
    timestamp = int(time.time() if for_time is None else for_time)
    counter = timestamp // period
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1_000_000:06d}"


def verify_totp_code(secret: str, code: str, *, window: int = 2) -> bool:
    cleaned = code.strip().replace(" ", "").replace("-", "")
    if not cleaned.isdigit():
        return False
    now = int(time.time())
    for offset in range(-window, window + 1):
        candidate = generate_totp_code(secret, for_time=now + offset * 30)
        if hmac.compare_digest(candidate, cleaned):
            return True
    return False
