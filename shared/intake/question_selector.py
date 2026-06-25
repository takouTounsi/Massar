"""Deterministic next-question selection.

Strict priority (hard invariant #1 — no LLM, fully traceable):
  a. pending probes (contextually relevant now);
  b. else the highest information-value askable question, respecting
     preconditions and the 4-phase progressive disclosure;
  c. else TERMINATE (DiagnosticReady) — we do not run a fixed form to the end.

  info_value(q) = sum over q.targets of m.value * (1 - confidence(field))
"""

from __future__ import annotations

from shared.contracts.enums import IntakePhase
from shared.intake.contracts import IntakeQuestion, IntakeState, evaluate_condition
from shared.intake.missing_info import compute_missing
from shared.intake.question_bank import QUESTIONS, QUESTIONS_BY_ID

PHASE_ORDER: list[IntakePhase] = [
    IntakePhase.FOUNDATION,
    IntakePhase.MARKET_CLIENTS,
    IntakePhase.MODEL_LEGAL,
    IntakePhase.FINANCE_TEAM,
]

# Selection tuning.
THRESHOLD = 0.2  # below this, a question adds too little to be worth asking
DEFAULT_TARGET_VALUE = 0.4  # value of a target not currently on the missing frontier
DECLARED_STAGE_VALUE = 0.9  # the one-time self-assessment is worth asking early
NEUTRAL_VALUE = 0.5  # context questions (e.g. sector) with no registry target


def _confidence(state: IntakeState, field: str) -> float:
    entry = state.ledger.get(field)
    return entry.confidence if entry else 0.0


def _preconditions_ok(question: IntakeQuestion, state: IntakeState) -> bool:
    return all(
        evaluate_condition(cond, state.profile, state.ledger) for cond in question.preconditions
    )


def _already_handled(question: IntakeQuestion, state: IntakeState) -> bool:
    return (
        question.id in state.asked_question_ids
        or question.id in state.answered_by_inference
    )


def info_value(
    question: IntakeQuestion, state: IntakeState, missing_value: dict[str, float]
) -> float:
    total = 0.0
    for field in question.targets:
        value = missing_value.get(field, DEFAULT_TARGET_VALUE)
        total += value * (1.0 - _confidence(state, field))
    if question.captures_declared_stage and not state.declared_stage_captured:
        total = max(total, DECLARED_STAGE_VALUE)
    if not question.targets and not question.captures_declared_stage:
        total = max(total, NEUTRAL_VALUE)
    return total


def select_next(state: IntakeState) -> IntakeQuestion | None:
    # a. Pending probes are contextually relevant right now.
    for probe_id in state.pending_probes:
        question = QUESTIONS_BY_ID.get(probe_id)
        if question is None or _already_handled(question, state):
            continue
        if _preconditions_ok(question, state):
            return question

    # b. Highest info-value askable question, phase by phase.
    missing_value = {item.field: item.value for item in compute_missing(state)}
    for phase in PHASE_ORDER:
        candidates: list[tuple[float, IntakeQuestion]] = []
        for question in QUESTIONS:
            if question.is_probe or question.phase != phase:
                continue
            if _already_handled(question, state) or not _preconditions_ok(question, state):
                continue
            candidates.append((info_value(question, state, missing_value), question))
        if not candidates:
            continue
        candidates.sort(key=lambda pair: (pair[0], pair[1].id), reverse=True)
        best_value, best_question = candidates[0]
        if best_value > THRESHOLD:
            return best_question
        # Phase exhausted (all remaining low-value) -> advance to the next phase.

    # c. Nothing left worth asking.
    return None
