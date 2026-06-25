"""PML (Perceived Maturity Level) integration tests.

The Classification Service's PML is the founder's self-assessment — our
``declared_stage`` (§9.6). These tests prove the boundary behaves correctly:

  * the adapter maps their generic phase vocabulary onto our S-stages (Step 4);
  * an over- and an under-estimation flow through ``adapt_pml`` -> the existing
    gap path with the correct gap *direction* (Step 4);
  * PML stays an OPINION: it never enters the evidence ledger and never changes
    which question is selected (the isolation invariant).

The partner's classifier code (``services/classification_service``,
``shared/application/startup_classifier.py``) is NOT on this branch, so we do not
import it. Instead we drive the adapter with the exact deterministic terminal
payload its ``USE_DEMO_CLASSIFIER=1`` path emits (the ``StartupResultPayload``
shape: ``phase`` + ``transcript``). When their branch merges, the same payload
shape applies unchanged.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from shared.contracts.enums import EvidenceStatus, GapLevel, MaturityStage
from shared.domain.diagnosis import build_diagnosis
from shared.domain.utils import STAGE_ORDER
from shared.intake import Extractor, InMemorySessionStore, IntakeEngine, adapt_pml
from shared.intake.contracts import LedgerEntry
from shared.intake.question_selector import select_next

# --- helpers ---


def _demo_pml_payload(phase: str) -> dict[str, Any]:
    """A terminal payload shaped exactly like the Classification Service emits
    (StartupResultPayload / ResultPayload) under USE_DEMO_CLASSIFIER=1."""

    return {
        "session_industry_key": "fintech",
        "session_id": "demo-session-1",
        "node_id": f"fintech_res_{phase.lower()}",
        "phase": phase,
        "result_text": f"Phase : {phase} — Secteur Fintech.",
        "transcript": [
            {
                "node_id": "fintech_root_entity",
                "question": "Avez-vous créé une entité légale ?",
                "chosen_answer_text": "Pas encore",
            }
        ],
        "is_terminal": True,
    }


def _ledger(**fields: tuple[Any, EvidenceStatus]) -> dict[str, LedgerEntry]:
    return {
        name: LedgerEntry(field=name, value=value, status=status)
        for name, (value, status) in fields.items()
    }


def _s1_ledger() -> dict[str, LedgerEntry]:
    """Evidence only supports S1 (no S2 gate confirmed) -> diagnosed IDEATION."""

    return _ledger(problem_validated=(False, EvidenceStatus.MISSING))


def _s4_ledger() -> dict[str, LedgerEntry]:
    """All gates through S4 confirmed -> diagnosed FUNDRAISING."""

    C = EvidenceStatus.CONFIRMED
    return _ledger(
        problem_validated=(True, C),
        documented_interviews=(8, C),
        has_prototype=(True, C),
        has_legal_entity=(True, C),
        team_size=(3, C),
        legal_form=("SARL", C),
        invoices_with_vat=(True, C),
        paying_customers=(4, C),
    )


def _engine(answers: dict[str, dict[str, Any]] | None = None) -> IntakeEngine:
    payloads = answers or {}

    class Scripted:
        async def generate(self, prompt: str, context: dict[str, Any]) -> str:
            return json.dumps(payloads.get(context["question_id"], {"extracted": {}}))

    return IntakeEngine(extractor=Extractor(Scripted()), session_store=InMemorySessionStore())


# --- Step 4a: the mapping table ---


def test_adapter_maps_phase_vocabulary_to_our_stages() -> None:
    expected = {
        "IDEATION": "S1",
        "POC_MVP": "S3",
        "PMF": "S4",
        "SCALE": "S5",
        "GROWTH": "S6",
    }
    for phase, stage in expected.items():
        adapted = adapt_pml(_demo_pml_payload(phase))
        assert adapted.recognized is True
        assert adapted.declared_stage == stage


def test_adapter_flags_conservative_approximations() -> None:
    # Straddling phases are mapped down and flagged; exact ones are not.
    assert adapt_pml(_demo_pml_payload("IDEATION")).approximated is True
    assert adapt_pml(_demo_pml_payload("SCALE")).approximated is True
    assert adapt_pml(_demo_pml_payload("PMF")).approximated is False


def test_adapter_is_defensive_on_bad_payloads() -> None:
    # None, non-mapping, missing phase, unknown phase -> recognized=False, no crash.
    for bad in (None, [], "nope", {}, {"phase": ""}, {"phase": "WAT"}, {"phase": "UNKNOWN_PHASE"}):
        adapted = adapt_pml(bad)  # type: ignore[arg-type]
        assert adapted.recognized is False
        assert adapted.declared_stage is None

    # Extra/missing fields are tolerated; transcript is copied opaquely.
    payload = _demo_pml_payload("PMF")
    payload["unexpected_field"] = {"nested": 1}
    adapted = adapt_pml(payload)
    assert adapted.recognized is True
    assert adapted.transcript and adapted.transcript[0]["node_id"] == "fintech_root_entity"


# --- Step 4a: PML -> adapter -> gap path, both directions ---


def _gap_direction(declared: MaturityStage, diagnosed: MaturityStage) -> str:
    delta = STAGE_ORDER[declared] - STAGE_ORDER[diagnosed]
    if delta > 0:
        return "over"
    if delta < 0:
        return "under"
    return "none"


def test_pml_overestimation_gap_direction() -> None:
    # Founder's PML says GROWTH (-> S6 -> GROWTH); evidence only supports S1.
    engine = _engine()
    state = engine.start_session()
    engine.apply_pml(state.session_id, _demo_pml_payload("GROWTH"))
    state = engine.get_state(state.session_id)
    assert state is not None
    state.ledger = _s1_ledger()

    diagnosis = build_diagnosis(state).diagnosis
    assert diagnosis.declared_stage == MaturityStage.GROWTH
    assert diagnosis.diagnosed_stage == MaturityStage.IDEATION
    assert _gap_direction(diagnosis.declared_stage, diagnosis.diagnosed_stage) == "over"
    assert diagnosis.gap_level == GapLevel.HIGH


def test_pml_underestimation_gap_direction() -> None:
    # Founder's PML says IDEATION (-> S1); evidence supports S4 (FUNDRAISING).
    engine = _engine()
    state = engine.start_session()
    engine.apply_pml(state.session_id, _demo_pml_payload("IDEATION"))
    state = engine.get_state(state.session_id)
    assert state is not None
    state.ledger = _s4_ledger()

    diagnosis = build_diagnosis(state).diagnosis
    assert diagnosis.declared_stage == MaturityStage.IDEATION
    assert diagnosis.diagnosed_stage == MaturityStage.FUNDRAISING
    assert _gap_direction(diagnosis.declared_stage, diagnosis.diagnosed_stage) == "under"


def test_pml_not_computed_when_absent() -> None:
    # PML is optional: no payload -> declared_stage stays None, engine still runs.
    engine = _engine()
    state = engine.start_session()
    engine.apply_pml(state.session_id, {"phase": "UNKNOWN_PHASE"})
    state = engine.get_state(state.session_id)
    assert state is not None
    assert state.declared_stage is None


# --- Step 4b: the isolation invariant ---


def test_pml_never_enters_the_evidence_ledger() -> None:
    engine = _engine()
    state = engine.start_session()
    engine.apply_pml(state.session_id, _demo_pml_payload("GROWTH"))
    state = engine.get_state(state.session_id)
    assert state is not None

    # The declared signal and the partner's phase string are nowhere in the ledger.
    assert "declared_stage" not in state.ledger
    assert all(entry.value not in {"GROWTH", "S6"} for entry in state.ledger.values())
    # The transcript is kept only as opaque perception context, not as evidence.
    assert state.pml_transcript and not state.ledger


def test_pml_does_not_change_question_selection() -> None:
    # Identical sessions; one gets PML injected, the other does not. The next
    # selected question must be identical -> PML did not bias selection.
    control = _engine()
    c_state = control.start_session()

    treated = _engine()
    t_state = treated.start_session()
    treated.apply_pml(t_state.session_id, _demo_pml_payload("GROWTH"))
    t_state = treated.get_state(t_state.session_id)
    assert t_state is not None

    assert select_next(c_state).id == select_next(t_state).id
    # The inline self-assessment question's lifecycle flag is untouched by PML, so
    # it is still asked exactly as before.
    assert t_state.declared_stage_captured is False


# --- Step 3: source-of-truth rule (PML authoritative, inline fallback) ---


def test_pml_is_authoritative_over_inline_answer() -> None:
    declared = {"value": "S2", "status": "CONFIRMED"}
    answers = {"q_declared_stage": {"extracted": {"declared_stage": declared}}}
    engine = _engine(answers)
    state = engine.start_session()
    engine.apply_pml(state.session_id, _demo_pml_payload("GROWTH"))  # -> S6

    state = asyncio.run(
        engine.process_answer(state.session_id, "je pense être en S2", "q_declared_stage")
    )
    assert state is not None
    assert state.declared_stage == "S6"  # PML wins
    assert state.declared_stage_source == "pml"
    assert state.declared_stage_captured is True  # inline question still consumed


def test_inline_answer_used_as_fallback_without_pml() -> None:
    declared = {"value": "S2", "status": "CONFIRMED"}
    answers = {"q_declared_stage": {"extracted": {"declared_stage": declared}}}
    engine = _engine(answers)
    state = engine.start_session()

    state = asyncio.run(
        engine.process_answer(state.session_id, "je pense être en S2", "q_declared_stage")
    )
    assert state is not None
    assert state.declared_stage == "S2"
    assert state.declared_stage_source == "inline"
