from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HASH_NAME = "pbkdf2_sha256"
HASH_ITERATIONS = 5_000


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> None:
    if not EMAIL_RE.match(normalize_email(email)):
        raise ValueError("Invalid email address")


def validate_password_policy(password: str) -> None:
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one symbol")


def hash_password(password: str) -> str:
    salt = base64.urlsafe_b64encode(os.urandom(18)).decode("ascii").rstrip("=")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), HASH_ITERATIONS)
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{HASH_NAME}${HASH_ITERATIONS}${salt}${encoded}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected = password_hash.split("$", 3)
        if algorithm != HASH_NAME:
            return False
        iterations = int(iterations_raw)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return hmac.compare_digest(encoded, expected)
