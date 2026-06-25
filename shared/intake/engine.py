"""Thin orchestrator for the adaptive intake turn loop.

All intelligence lives in the declarative data (question_bank, requirements) and
the deterministic modules (probe_engine, missing_info, question_selector,
contradiction_detector). This class only sequences them. The single LLM call is
the extractor; everything else is rule-driven and traceable.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from shared.contracts.enums import EvidenceStatus
from shared.intake.contracts import (
    AnswerRecord,
    IntakeQuestion,
    IntakeState,
    LedgerEntry,
)
from shared.intake.contradiction_detector import detect_contradictions
from shared.intake.extractor import Extractor, redact_pii
from shared.intake.pml_adapter import adapt_pml
from shared.intake.probe_engine import evaluate_probes
from shared.intake.profile_writer import InMemoryProfileWriter, ProfileWriter
from shared.intake.question_bank import QUESTIONS_BY_ID
from shared.intake.question_selector import select_next
from shared.intake.session_manager import InMemorySessionStore, SessionStore

logger = logging.getLogger("intake.engine")

_PROTECTED = (EvidenceStatus.CONFIRMED, EvidenceStatus.CONTRADICTED)


class IntakeEngine:
    def __init__(
        self,
        extractor: Extractor,
        session_store: SessionStore | None = None,
        profile_writer: ProfileWriter | None = None,
    ) -> None:
        self._extractor = extractor
        self._sessions = session_store or InMemorySessionStore()
        self._writer = profile_writer or InMemoryProfileWriter()

    # --- lifecycle ---

    def start_session(self, project_id: UUID | None = None, lang: str = "fr") -> IntakeState:
        state = IntakeState(project_id=project_id or uuid4(), lang=lang)
        self._advance(state)
        self._sessions.save(state)
        self._writer.persist(state)
        return state

    def get_state(self, session_id: UUID) -> IntakeState | None:
        return self._sessions.get(session_id)

    def resume(self, session_id: UUID) -> IntakeState | None:
        """Rehydrate from the persisted session, re-run selection, continue."""

        state = self._sessions.get(session_id)
        if state is None:
            return None
        if not state.completed:
            self._advance(state)
            self._sessions.save(state)
        return state

    def apply_pml(
        self, session_id: UUID, payload: Mapping[str, Any] | None
    ) -> IntakeState | None:
        """Feed a Classification Service PML payload into the declared/gap side.

        PML is the founder's self-assessment, i.e. our ``declared_stage`` (§9.6): an
        opinion to be verified, never evidence. It is mapped at the boundary
        (``adapt_pml``) and written ONLY to the declared side. It deliberately does
        not touch ``declared_stage_captured`` — the inline ``q_declared_stage`` is
        still asked exactly as before, so injecting PML never changes which question
        is selected (the isolation invariant). PML is authoritative when both it and
        the inline answer exist.

        PML is optional: an unrecognized/empty payload leaves the session untouched
        (the gap is simply not computed) and never raises.
        """

        state = self._sessions.get(session_id)
        if state is None:
            return None

        adapted = adapt_pml(payload)
        # Keep the transcript as opaque perception-layer context regardless — it is
        # never fed to the extractor or written to the ledger.
        state.pml_transcript = [dict(entry) for entry in adapted.transcript]
        if not adapted.recognized:
            # No usable declared signal; leave declared_stage as-is (inline may set it).
            self._sessions.save(state)
            self._writer.persist(state)
            return state

        state.declared_stage = adapted.declared_stage
        state.declared_stage_source = "pml"
        self._sessions.save(state)
        self._writer.persist(state)
        return state

    # --- turn loop ---

    async def process_answer(
        self, session_id: UUID, raw_answer: str, question_id: str
    ) -> IntakeState | None:
        state = self._sessions.get(session_id)
        if state is None:
            return None
        question = QUESTIONS_BY_ID.get(question_id)
        if question is None:
            return state

        # Store a PII-redacted copy of the answer; extraction still sees the original.
        answer = AnswerRecord(question_id=question_id, raw_answer=redact_pii(raw_answer))
        state.answers.append(answer)
        # Record the answered question so it is never re-selected, even if a client
        # answers out of order.
        if question_id not in state.asked_question_ids:
            state.asked_question_ids.append(question_id)

        # 1. EXTRACT (the only LLM call).
        result = await self._extractor.extract(question, raw_answer, state.lang)
        if result.degraded:
            logger.warning(
                "extraction_degraded session=%s question=%s", state.session_id, question_id
            )

        if question.captures_declared_stage:
            # declared_stage is captured once, isolated; never feeds the engine.
            declared = result.extracted.get("declared_stage")
            # PML from the Classification Service is authoritative for the declared
            # side; our inline question is only the fallback when their service did
            # not run. So we only adopt the inline answer if PML did not set it.
            if declared is not None and state.declared_stage_source != "pml":
                state.declared_stage = str(declared)
                state.declared_stage_source = "inline"
            state.declared_stage_captured = True
        else:
            for field, status in result.evidence_status.items():
                value = result.extracted.get(field)
                self._write(state, field, value, status, answer.answer_id)

        # Unprompted signals: never re-ask volunteered info -> record UNVERIFIED.
        for field, value in result.unprompted_signals.items():
            self._write(
                state, field, value, EvidenceStatus.UNVERIFIED, answer.answer_id, prompted=False
            )

        # founding_date stored early (temporal severity hook).
        if state.profile.get("founding_date") and not state.founding_date:
            state.founding_date = str(state.profile["founding_date"])

        # 2. UPDATE: reconcile contradictions, then persist durably.
        detect_contradictions(state)
        self._writer.persist(state, answer)

        # 3. PROBES.
        evaluate_probes(state)

        # 4-5. MISSING-INFO + SELECT next question.
        self._advance(state)
        self._sessions.save(state)
        return state

    # --- helpers ---

    def _write(
        self,
        state: IntakeState,
        field: str,
        value: Any,
        status: EvidenceStatus,
        answer_id: str,
        *,
        prompted: bool = True,
    ) -> None:
        status = EvidenceStatus(status)
        existing = state.ledger.get(field)
        if not prompted and existing is not None and EvidenceStatus(existing.status) in _PROTECTED:
            # Volunteered info must never downgrade a confirmed/contradicted field.
            return
        if status is EvidenceStatus.MISSING:
            # Record that we asked and got nothing, without clobbering prior evidence.
            if existing is None:
                state.ledger[field] = LedgerEntry(
                    field=field, value=None, status=EvidenceStatus.MISSING,
                    source_answer_id=answer_id, updated_at=datetime.now(UTC),
                )
            return
        state.profile[field] = value
        state.ledger[field] = LedgerEntry(
            field=field,
            value=value,
            status=status,
            source_answer_id=answer_id,
            updated_at=datetime.now(UTC),
        )

    def _advance(self, state: IntakeState) -> None:
        """Select the next question and update bookkeeping/phase."""

        question: IntakeQuestion | None = select_next(state)
        if question is None:
            state.completed = True
            state.current_question_id = None
            return
        state.completed = False
        state.current_question_id = question.id
        state.phase = question.phase
        if question.id not in state.asked_question_ids:
            state.asked_question_ids.append(question.id)
        if question.id in state.pending_probes:
            state.pending_probes.remove(question.id)
