"""Session CRUD + lifecycle for the intake engine.

A Redis-backed store for production with an in-memory fallback so the engine and
its tests stay deterministic without a running Redis. ``redis`` is imported
lazily so the dependency is optional at runtime/test time.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from shared.intake.contracts import IntakeState

_KEY_PREFIX = "intake:session:"


class SessionStore(Protocol):
    def get(self, session_id: UUID) -> IntakeState | None: ...
    def save(self, state: IntakeState) -> None: ...
    def delete(self, session_id: UUID) -> None: ...


class InMemorySessionStore:
    """Process-local store. Default for local/dev and the test suite."""

    def __init__(self) -> None:
        self._states: dict[str, str] = {}

    def get(self, session_id: UUID) -> IntakeState | None:
        raw = self._states.get(str(session_id))
        if raw is None:
            return None
        return IntakeState.model_validate_json(raw)

    def save(self, state: IntakeState) -> None:
        self._states[str(state.session_id)] = state.model_dump_json()

    def delete(self, session_id: UUID) -> None:
        self._states.pop(str(session_id), None)


class RedisSessionStore:
    """Redis-backed store. State is serialized as JSON under ``intake:session:*``."""

    def __init__(self, url: str, ttl_seconds: int = 60 * 60 * 24) -> None:
        import redis  # lazy: dependency is optional

        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds

    def get(self, session_id: UUID) -> IntakeState | None:
        raw = self._client.get(f"{_KEY_PREFIX}{session_id}")
        if raw is None:
            return None
        return IntakeState.model_validate_json(raw)

    def save(self, state: IntakeState) -> None:
        self._client.set(
            f"{_KEY_PREFIX}{state.session_id}",
            state.model_dump_json(),
            ex=self._ttl,
        )

    def delete(self, session_id: UUID) -> None:
        self._client.delete(f"{_KEY_PREFIX}{session_id}")


def build_session_store(redis_url: str | None) -> SessionStore:
    """Pick a store: Redis when a URL is configured and importable, else memory."""

    if redis_url:
        try:
            return RedisSessionStore(redis_url)
        except Exception:  # pragma: no cover - redis missing/unreachable -> degrade
            return InMemorySessionStore()
    return InMemorySessionStore()
