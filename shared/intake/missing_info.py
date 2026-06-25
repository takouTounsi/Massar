"""Frontier-relative missing-info computation.

Dry-evaluates the stage gates from the shared requirements registry WITHOUT
importing the classifier/scorer (hard invariant #5). We only ask what could
change the verdict: the unmet gates of the *next* stage, plus fundamental
scoring fields with no evidence. Present-but-negative fields are surfaced as
structural blockers, not questions (hard invariant: missing-info is
frontier-relative, not "fill every field").
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.contracts.enums import EvidenceStage, EvidenceStatus, MissingKind
from shared.intake.contracts import IntakeState, MissingItem
from shared.intake.requirements import (
    REQUIREMENTS,
    RequirementSpec,
    fundamental_specs,
    gate_satisfied,
    gate_specs,
    next_stage,
)
from shared.intake.requirements import frontier_stage as _frontier_from_ledger

GATE_VALUE = 1.0
FUNDAMENTAL_VALUE = 0.8


def _status(state: IntakeState, field: str) -> EvidenceStatus:
    entry = state.ledger.get(field)
    return EvidenceStatus(entry.status) if entry else EvidenceStatus.MISSING


def _value(state: IntakeState, field: str) -> object:
    entry = state.ledger.get(field)
    if entry is not None and entry.value is not None:
        return entry.value
    return state.profile.get(field)


def frontier_stage(state: IntakeState) -> EvidenceStage:
    """Highest contiguous stage whose gates are all satisfied (S1 is free).

    Delegates to the shared registry function so the engine and the downstream
    classifier compute the frontier identically from the same ledger contract.
    """

    return _frontier_from_ledger(state.ledger)


@dataclass(frozen=True)
class FrontierProgress:
    """Frontier-relative progress (invariant §9.5): how close the evidence is to
    the *next* stage, NOT answered/total over a fixed field set.

    ``percent_to_next`` is the share of the next stage's gates already satisfied;
    at the top stage (S6, no next) progress is complete by definition.
    """

    frontier_stage: EvidenceStage
    next_stage: EvidenceStage | None
    gates_satisfied: int
    gates_total: int
    percent_to_next: float


def frontier_progress(state: IntakeState) -> FrontierProgress:
    """Compute progress relative to the current evidence frontier.

    Reuses the same gate predicate the classifier uses (``gate_satisfied``), so a
    project capped at S2 reports its real distance to S3 instead of a misleading
    confirmed/13 fraction.
    """

    frontier = frontier_stage(state)
    target = next_stage(frontier)
    if target is None:
        # Top of the document-gated taxonomy: nothing further to gate.
        return FrontierProgress(frontier, None, 0, 0, 100.0)
    specs = gate_specs(target)
    total = len(specs)
    satisfied = sum(1 for spec in specs if gate_satisfied(state.ledger, spec))
    percent = round(100.0 * satisfied / total, 1) if total else 100.0
    return FrontierProgress(frontier, target, satisfied, total, percent)


def compute_missing(state: IntakeState) -> list[MissingItem]:
    items: list[MissingItem] = []
    seen: set[str] = set()

    target = next_stage(frontier_stage(state))
    if target is not None:
        for spec in gate_specs(target):
            item = _classify(state, spec, gates_next_stage=True)
            if item is not None:
                items.append(item)
                seen.add(spec.field)

    # Fundamental scoring fields with no evidence are always high value.
    for spec in fundamental_specs():
        if spec.field in seen:
            continue
        if _status(state, spec.field) is EvidenceStatus.MISSING:
            items.append(
                MissingItem(
                    field=spec.field,
                    kind=MissingKind.ASKABLE,
                    value=FUNDAMENTAL_VALUE,
                    reason="fundamental scoring field with no evidence",
                )
            )
            seen.add(spec.field)

    items.sort(key=lambda item: item.value, reverse=True)
    return items


def _classify(
    state: IntakeState, spec: RequirementSpec, *, gates_next_stage: bool
) -> MissingItem | None:
    status = _status(state, spec.field)
    base = GATE_VALUE if gates_next_stage else 0.0
    if spec.fundamental:
        base += FUNDAMENTAL_VALUE

    if status is EvidenceStatus.CONFIRMED:
        if spec.gate.is_negative(_value(state, spec.field)):
            # Present but negative (e.g. team_size == 1 at S3): a blocker, not a question.
            return MissingItem(
                field=spec.field,
                kind=MissingKind.STRUCTURAL_GAP,
                value=0.0,
                gates_next_stage=gates_next_stage,
                reason="present but does not meet the gate (structural blocker)",
            )
        return None  # satisfied gate

    if status is EvidenceStatus.MISSING:
        # Distinguish absent vs present-but-negative (the latter is structural).
        value = _value(state, spec.field)
        if value is not None and spec.gate.is_negative(value):
            return MissingItem(
                field=spec.field,
                kind=MissingKind.STRUCTURAL_GAP,
                value=0.0,
                gates_next_stage=gates_next_stage,
                reason="present but does not meet the gate (structural blocker)",
            )
        return MissingItem(
            field=spec.field,
            kind=MissingKind.ASKABLE,
            value=base,
            gates_next_stage=gates_next_stage,
            reason="gates the next stage and has no evidence",
        )

    if status in (EvidenceStatus.UNVERIFIED, EvidenceStatus.CONTRADICTED):
        return MissingItem(
            field=spec.field,
            kind=MissingKind.NEEDS_PROBE,
            value=base * 0.6,
            gates_next_stage=gates_next_stage,
            reason=f"{status.value.lower()} — needs an evidence probe",
        )
    return None


def field_to_questions() -> dict[str, list[str]]:
    """Reverse map evidence field -> question ids that target it (for selection)."""

    from shared.intake.question_bank import QUESTIONS

    mapping: dict[str, list[str]] = {field: [] for field in REQUIREMENTS}
    for question in QUESTIONS:
        for field in question.targets:
            mapping.setdefault(field, []).append(question.id)
    return mapping
