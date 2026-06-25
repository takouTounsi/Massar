"""Runtime handoff: intake evidence ledger -> downstream diagnosis (R2).

The maturity predictor and the scorer already exist and are unit-tested; they were
simply never called outside tests, and the ledger never left the intake service.
This module is the thin bridge that:

  1. projects the engine's shared profile (a loose ``dict``) onto the typed
     ``ProjectProfile`` contract the scorer consumes,
  2. runs the EXISTING ``LedgerMaturityPredictor`` and ``WeightedRuleScoreCalculator``
     on the live evidence ledger,
  3. returns a single ``DiagnosisResponse``.

It reuses the tested functions verbatim — no maturity/scoring logic is
reimplemented here. The intake engine still never assigns a stage (§9.1): the
stage is produced only by the predictor invoked below.
"""

from __future__ import annotations

from typing import Any

from shared.contracts.schemas import ProjectProfile
from shared.domain.maturity import LedgerMaturityPredictor, _declared_to_maturity
from shared.domain.scoring import WeightedRuleScoreCalculator
from shared.intake.contracts import DiagnosisResponse, IntakeState
from shared.intake.missing_info import frontier_stage

# Natural-language clarity/novelty tiers (collected by q_revenue_model / q_innovation
# as enums) mapped onto the scorer's 0-100 contract fields. Keeps the intake layer
# gradeable in plain language while the scoring layer stays numeric.
_REVENUE_MODEL_SCALE: dict[str, int] = {"clear": 80, "partial": 50, "unclear": 25}
_INNOVATION_SCALE: dict[str, int] = {"high": 80, "medium": 55, "low": 30}


def _as_int_scale(value: Any, scale: dict[str, int]) -> int | None:
    """Coerce an enum tier or a raw 0-100 number onto the scorer's int field."""

    if value is None:
        return None
    if isinstance(value, str):
        return scale.get(value.strip().lower())
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def project_profile_from_state(state: IntakeState) -> ProjectProfile:
    """Build the typed ``ProjectProfile`` the scorer needs from the loose profile.

    Only fields the intake engine actually collects are mapped; everything else
    keeps its contract default so the scorer degrades gracefully (and the ledger,
    not these values, drives confidence via ``calculate_with_ledger``).
    """

    profile = state.profile
    paying = profile.get("paying_customers")
    has_revenue = bool(profile.get("invoices_with_vat")) or bool(paying)

    data: dict[str, Any] = {
        "project_id": state.project_id,
        "declared_stage": _declared_to_maturity(state.declared_stage),
        "sector": profile.get("sector") or "technology",
        "legal_form": profile.get("legal_form"),
        "formalization_status": profile.get("formalization_status"),
        "team_size": profile.get("team_size"),
        "has_mvp": profile.get("has_prototype"),
        "has_revenue": has_revenue,
        "monthly_revenue": profile.get("monthly_revenue"),
        "recurring_revenue": profile.get("recurring_revenue"),
        "paying_customers": paying,
        "documented_interviews": profile.get("documented_interviews"),
        "market_size_known": profile.get("market_size_known"),
        "process_automation_level": profile.get("process_automation_level"),
        "revenue_model_clarity": _as_int_scale(
            profile.get("revenue_model_clarity"), _REVENUE_MODEL_SCALE
        ),
        "innovation_level": _as_int_scale(profile.get("innovation_level"), _INNOVATION_SCALE),
    }
    # Drop None so the contract defaults (and ge/le validators) apply cleanly.
    data = {key: value for key, value in data.items() if value is not None}
    return ProjectProfile(**data)


def build_diagnosis(state: IntakeState) -> DiagnosisResponse:
    """Run the existing predictor + scorer on the live ledger and package the result."""

    predictor = LedgerMaturityPredictor()
    diagnosis = predictor.predict(
        state.ledger,
        declared_stage=state.declared_stage,
        founding_date=state.founding_date,
    )

    profile = project_profile_from_state(state)
    scores = WeightedRuleScoreCalculator().calculate_with_ledger(profile, state.ledger)

    return DiagnosisResponse(
        session_id=state.session_id,
        completed=state.completed,
        frontier_stage=frontier_stage(state),
        declared_stage=state.declared_stage,
        diagnosis=diagnosis,
        scores=scores,
        ledger=state.ledger,
    )
