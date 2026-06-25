"""Tunisian regulatory-coherence contradiction detection.

Reconciles the updated profile against existing evidence. When a rule matches,
the offending field is flagged ``CONTRADICTED`` (never silently averaged or
overwritten) and a clarification probe is queued. Fully deterministic — no LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared.contracts.enums import EvidenceStatus
from shared.intake.contracts import ContradictionRule, IntakeState, LedgerEntry, evaluate_condition
from shared.intake.question_bank import CONTRADICTION_RULES


def detect_contradictions(
    state: IntakeState, rules: list[ContradictionRule] | None = None
) -> list[dict[str, object]]:
    """Flag contradictions on ``state`` in place. Returns the new contradictions."""

    found: list[dict[str, object]] = []
    already = {entry.get("rule_id") for entry in state.contradictions}
    for rule in rules if rules is not None else CONTRADICTION_RULES:
        if not all(evaluate_condition(cond, state.profile, state.ledger) for cond in rule.when):
            continue

        field = rule.contradicted_field
        existing = state.ledger.get(field)
        # Re-apply the flag every turn the conditions hold: a later direct answer
        # to ``field`` must not silently clear an unresolved contradiction.
        # Preserve the prior value; never average it away.
        state.ledger[field] = LedgerEntry(
            field=field,
            value=existing.value if existing else state.profile.get(field),
            status=EvidenceStatus.CONTRADICTED,
            source_answer_id=existing.source_answer_id if existing else None,
            note=rule.reason.get(state.lang) or rule.reason.get("fr"),
            updated_at=datetime.now(UTC),
        )
        if rule.id in already:
            continue  # record + probe already raised; just keep the flag applied

        record: dict[str, object] = {
            "rule_id": rule.id,
            "field": field,
            "reason": rule.reason.get(state.lang) or rule.reason.get("fr", ""),
        }
        state.contradictions.append(record)
        found.append(record)

        # Push the clarification probe so the user can resolve it.
        if rule.clarification_probe and rule.clarification_probe not in state.pending_probes:
            if rule.clarification_probe not in state.asked_question_ids:
                state.pending_probes.append(rule.clarification_probe)

    return found
