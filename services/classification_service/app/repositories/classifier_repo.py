"""Simple in-memory repository for storing classification sessions/results.

This is intentionally lightweight: swap with a DB-backed implementation
in a production service (SQLAlchemy repository, Redis, etc.). The Intake
Engine will read perceived states from this store and validate claims.
"""
from __future__ import annotations

from typing import Dict, Any
from threading import Lock


_STORE: Dict[str, Dict[str, Any]] = {}
_LOCK = Lock()


def save_session(session_id: str, session_data: Dict[str, Any]) -> None:
    with _LOCK:
        _STORE[session_id] = session_data


def get_session(session_id: str) -> Dict[str, Any] | None:
    return _STORE.get(session_id)


def save_result(session_id: str, result: Dict[str, Any]) -> None:
    with _LOCK:
        entry = _STORE.setdefault(session_id, {})
        entry.setdefault("results", []).append(result)


def list_sessions() -> Dict[str, Dict[str, Any]]:
    return dict(_STORE)
