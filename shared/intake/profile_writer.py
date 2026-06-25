"""Durable persistence of the profile + evidence ledger.

The authoritative live state lives in the session store (Redis); this writer is
the durable Postgres record. It persists the session payload, each answer (with
``source_answer_id`` + timestamp), and a profile snapshot, reusing the existing
JSONB tables (``intake_sessions`` / ``answers`` / ``project_profile_versions``)
so no new migration is required. An in-memory writer keeps the engine and tests
deterministic without a database.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from shared.intake.contracts import AnswerRecord, IntakeState


class ProfileWriter(Protocol):
    def persist(self, state: IntakeState, answer: AnswerRecord | None = None) -> None: ...


class InMemoryProfileWriter:
    """Records snapshots in process memory. Default for local/dev and tests."""

    def __init__(self) -> None:
        self.snapshots: list[dict[str, Any]] = []
        self.answers: list[AnswerRecord] = []

    def persist(self, state: IntakeState, answer: AnswerRecord | None = None) -> None:
        self.snapshots.append(state.model_dump(mode="json"))
        if answer is not None:
            self.answers.append(answer)


class PostgresProfileWriter:
    """Upserts the session and appends answers/snapshots to the JSONB tables."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def persist(self, state: IntakeState, answer: AnswerRecord | None = None) -> None:
        from sqlalchemy import text

        now = datetime.now(UTC)
        payload = state.model_dump(mode="json")
        ledger = {field: entry.model_dump(mode="json") for field, entry in state.ledger.items()}
        session = self._session_factory()
        try:
            session.execute(
                text(
                    "INSERT INTO intake_sessions (id, project_id, payload, created_at, "
                    "updated_at, version) VALUES (:id, :pid, CAST(:payload AS JSONB), :now, "
                    ":now, 1) ON CONFLICT (id) DO UPDATE SET payload = CAST(:payload AS JSONB), "
                    "updated_at = :now, version = intake_sessions.version + 1"
                ),
                {
                    "id": str(state.session_id),
                    "pid": str(state.project_id),
                    "payload": json.dumps(payload),
                    "now": now,
                },
            )
            session.execute(
                text(
                    "INSERT INTO project_profile_versions (id, project_id, payload, created_at, "
                    "updated_at, version) VALUES (:id, :pid, CAST(:payload AS JSONB), :now, "
                    ":now, 1)"
                ),
                {
                    "id": str(uuid4()),
                    "pid": str(state.project_id),
                    "payload": json.dumps({"profile": state.profile, "evidence_ledger": ledger}),
                    "now": now,
                },
            )
            if answer is not None:
                session.execute(
                    text(
                        "INSERT INTO answers (id, project_id, payload, created_at, updated_at, "
                        "version) VALUES (:id, :pid, CAST(:payload AS JSONB), :now, :now, 1)"
                    ),
                    {
                        "id": answer.answer_id,
                        "pid": str(state.project_id),
                        "payload": json.dumps(answer.model_dump(mode="json")),
                        "now": now,
                    },
                )
            session.commit()
        finally:
            session.close()
