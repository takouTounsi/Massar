from __future__ import annotations

from typing import Any

SENSITIVE_KEYS = {
    "email",
    "password",
    "password_hash",
    "access_token",
    "refresh_token",
    "temporary_login_token",
    "two_factor_secret",
    "pending_two_factor_secret",
    "monthly_revenue",
    "financial_capacity_score",
}


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key in SENSITIVE_KEYS else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value
