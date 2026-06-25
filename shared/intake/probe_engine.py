"""Declarative probe firing.

Evaluates probe trigger rules against the updated profile/ledger and mutates the
session state: queues EVIDENCE/SECTOR probe questions onto ``pending_probes`` and
applies STAGE_SKIP inferences. ``fire_once`` is enforced via ``fired_probes``.
This is fully deterministic — no LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared.contracts.enums import EvidenceStatus, ProbeKind
from shared.intake.contracts import IntakeState, LedgerEntry, ProbeRule, evaluate_condition
from shared.intake.question_bank import PROBE_RULES


def _matches(rule: ProbeRule, state: IntakeState) -> bool:
    return all(evaluate_condition(cond, state.profile, state.ledger) for cond in rule.trigger)


def evaluate_probes(state: IntakeState, rules: list[ProbeRule] | None = None) -> list[str]:
    """Fire eligible probes against ``state``. Returns the ids of rules fired."""

    fired: list[str] = []
    for rule in rules if rules is not None else PROBE_RULES:
        if rule.fire_once and rule.id in state.fired_probes:
            continue
        if not _matches(rule, state):
            continue

        if rule.kind is ProbeKind.EVIDENCE and rule.ask:
            _queue(state, rule.ask)
        elif rule.kind is ProbeKind.SECTOR:
            for question_id in rule.inject:
                if question_id not in state.enabled_probe_questions:
                    state.enabled_probe_questions.append(question_id)
                _queue(state, question_id)
        elif rule.kind is ProbeKind.STAGE_SKIP:
            for question_id in rule.mark_inferred:
                if question_id not in state.answered_by_inference:
                    state.answered_by_inference.append(question_id)
            for field in rule.confirm_fields:
                # Inference confirms a downstream basic; never overwrite a stronger
                # or contradicted signal that is already on record.
                existing = state.ledger.get(field)
                if existing and existing.status in (
                    EvidenceStatus.CONFIRMED,
                    EvidenceStatus.CONTRADICTED,
                ):
                    continue
                state.ledger[field] = LedgerEntry(
                    field=field,
                    value=True,
                    status=EvidenceStatus.CONFIRMED,
                    note="answered_by_inference",
                    updated_at=datetime.now(UTC),
                )

        state.fired_probes.append(rule.id)
        fired.append(rule.id)
    return fired


def _queue(state: IntakeState, question_id: str) -> None:
    if (
        question_id not in state.pending_probes
        and question_id not in state.asked_question_ids
    ):
        state.pending_probes.append(question_id)
