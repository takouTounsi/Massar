"""Deterministic tests for the Adaptive Intake Engine.

The LLM is always mocked: the engine must be deterministic without it. These
tests cover extraction scoping, persistence/resume, probe firing, missing-info
(including structural gaps), contradiction handling, selection priority, the
"je ne sais pas" path, and the Amira fixture case.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from shared.contracts.enums import EvidenceStage, EvidenceStatus, ProbeKind
from shared.intake import Extractor, InMemorySessionStore, IntakeEngine
from shared.intake.contracts import IntakeState
from shared.intake.missing_info import compute_missing, frontier_stage
from shared.intake.probe_engine import evaluate_probes
from shared.intake.question_bank import QUESTIONS_BY_ID
from shared.intake.question_selector import select_next


class ScriptedLLM:
    """Returns canned extraction JSON keyed by question id. No real model."""

    def __init__(self, answers: dict[str, dict[str, Any]]) -> None:
        self._answers = answers

    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        return json.dumps(self._answers.get(context["question_id"], {"extracted": {}}))


def _cell(value: Any, status: str = "CONFIRMED") -> dict[str, Any]:
    return {"value": value, "status": status}


def make_engine(answers: dict[str, dict[str, Any]]) -> IntakeEngine:
    return IntakeEngine(
        extractor=Extractor(ScriptedLLM(answers)),
        session_store=InMemorySessionStore(),
    )


def drive(engine: IntakeEngine, state: IntakeState, max_turns: int = 30) -> IntakeState:
    """Answer the current question until the engine terminates."""

    current = state
    for _ in range(max_turns):
        if current.completed or current.current_question_id is None:
            break
        nxt = asyncio.run(
            engine.process_answer(current.session_id, "réponse", current.current_question_id)
        )
        assert nxt is not None
        current = nxt
    return current


# --- Extraction (scoped schema) ---


def test_extractor_is_scoped_and_routes_unprompted_signals() -> None:
    extractor = Extractor(
        ScriptedLLM(
            {
                "q_clients": {
                    "extracted": {
                        "paying_customers": _cell(3),
                        "team_size": _cell(5),  # NOT in q_clients scope -> dropped
                    },
                    "unprompted_signals": {
                        "monthly_revenue": 1200,  # known field volunteered
                        "wat": "noise",  # unknown -> ignored
                    },
                }
            }
        )
    )
    result = asyncio.run(extractor.extract(QUESTIONS_BY_ID["q_clients"], "j'ai 3 clients", "fr"))

    assert result.extracted["paying_customers"] == 3
    assert "team_size" not in result.extracted  # cannot invent out-of-scope fields
    assert result.unprompted_signals == {"monthly_revenue": 1200}


def test_extractor_degrades_to_missing_on_non_json() -> None:
    class JunkLLM:
        async def generate(self, prompt: str, context: dict[str, Any]) -> str:
            return "not json at all"

    result = asyncio.run(Extractor(JunkLLM()).extract(QUESTIONS_BY_ID["q_clients"], "x", "fr"))
    assert result.extracted == {}
    assert result.evidence_status["paying_customers"] is EvidenceStatus.MISSING


# --- Persistence + resume ---


def test_session_persists_and_resumes() -> None:
    engine = make_engine({"q_sector": {"extracted": {"sector": _cell("saas")}}})
    state = engine.start_session(lang="fr")
    asyncio.run(engine.process_answer(state.session_id, "saas", "q_sector"))

    resumed = engine.resume(state.session_id)
    assert resumed is not None
    assert resumed.profile["sector"] == "saas"
    assert resumed.ledger["sector"].status == EvidenceStatus.CONFIRMED
    assert resumed.current_question_id is not None  # continues where it left off


# --- Probes ---


def test_evidence_probe_fires_on_traction_claim_without_invoices() -> None:
    state = IntakeState(profile={"claims_traction": True})
    fired = evaluate_probes(state)
    assert "rule_traction_evidence" in fired
    assert "probe_traction_evidence" in state.pending_probes


def test_sector_probe_injects_fintech_module() -> None:
    state = IntakeState(profile={"sector": "fintech"})
    fired = evaluate_probes(state)
    assert "rule_sector_fintech" in fired
    assert "probe_fintech_license" in state.enabled_probe_questions


def test_stage_skip_marks_basics_as_inferred() -> None:
    state = IntakeState(profile={"has_legal_entity": True, "invoices_with_vat": True})
    fired = evaluate_probes(state)
    assert "rule_skip_basics" in fired
    assert "q_idea" in state.answered_by_inference
    assert state.ledger["problem_validated"].note == "answered_by_inference"
    assert state.ledger["problem_validated"].status == EvidenceStatus.CONFIRMED


def test_probe_fires_once() -> None:
    state = IntakeState(profile={"sector": "fintech"})
    assert evaluate_probes(state) == ["rule_sector_fintech"]
    assert evaluate_probes(state) == []  # fire_once respected


# --- Missing-info (frontier-relative) ---


def test_missing_info_targets_next_stage_only() -> None:
    state = IntakeState()
    items = compute_missing(state)
    fields = {item.field for item in items}
    # Frontier is S1, so we ask the S2 gates, not every field in the registry.
    assert "problem_validated" in fields
    assert "documented_interviews" in fields
    assert "has_tva" not in fields  # an S5 gate is not on the frontier yet


def test_structural_gap_is_not_a_question() -> None:
    from shared.contracts.enums import MissingKind
    from shared.intake.contracts import LedgerEntry

    # team_size present but == 1 at the S3 gate: a blocker, not askable.
    state = IntakeState(
        profile={"problem_validated": True, "documented_interviews": 5, "team_size": 1,
                 "has_prototype": True, "has_legal_entity": True},
    )
    for field in ("problem_validated", "documented_interviews", "team_size",
                  "has_prototype", "has_legal_entity"):
        state.ledger[field] = LedgerEntry(
            field=field, value=state.profile[field], status=EvidenceStatus.CONFIRMED
        )
    items = {item.field: item for item in compute_missing(state)}
    assert items["team_size"].kind is MissingKind.STRUCTURAL_GAP
    assert items["team_size"].value == 0.0  # never selected as a question


# --- Contradiction ---


def test_recurring_clients_without_entity_is_contradicted() -> None:
    answers = {
        "q_clients": {
            "extracted": {
                "paying_customers": _cell(4),
                "claims_traction": _cell(True),
                "recurring_revenue": _cell(True),
            }
        },
        "q_legal_entity": {
            "extracted": {
                "has_legal_entity": _cell(False),
                "formalization_status": _cell("informal", "CONFIRMED"),
            }
        },
    }
    engine = make_engine(answers)
    state = engine.start_session()
    # Answer clients then legal-entity directly.
    asyncio.run(engine.process_answer(state.session_id, "clients récurrents", "q_clients"))
    state = asyncio.run(
        engine.process_answer(state.session_id, "pas d'entité", "q_legal_entity")
    )
    assert any(c["rule_id"] == "contradiction_recurring_no_entity" for c in state.contradictions)
    assert state.ledger["formalization_status"].status == EvidenceStatus.CONTRADICTED
    # The clarification probe was surfaced (queued, or already asked by selection).
    assert (
        "probe_clarify_formalization" in state.pending_probes
        or "probe_clarify_formalization" in state.asked_question_ids
    )


# --- Selection priority + edge cases ---


def test_pending_probe_is_selected_first() -> None:
    state = IntakeState(profile={"sector": "fintech"})
    state.asked_question_ids.append("q_sector")
    evaluate_probes(state)  # queues probe_fintech_license
    chosen = select_next(state)
    assert chosen is not None and chosen.id == "probe_fintech_license"


def test_declared_stage_is_isolated() -> None:
    engine = make_engine(
        {"q_declared_stage": {"extracted": {"declared_stage": _cell("S6")}}}
    )
    state = engine.start_session()
    state = asyncio.run(
        engine.process_answer(state.session_id, "je suis en croissance", "q_declared_stage")
    )
    assert state.declared_stage == "S6"
    assert state.declared_stage_captured is True
    assert "declared_stage" not in state.profile  # never feeds extraction/selection
    assert "declared_stage" not in state.ledger


def test_je_ne_sais_pas_marks_missing_without_looping() -> None:
    engine = make_engine(
        {"q_clients": {"extracted": {"paying_customers": {"value": None, "status": "MISSING"}}}}
    )
    state = engine.start_session()
    state = asyncio.run(engine.process_answer(state.session_id, "je ne sais pas", "q_clients"))
    assert state.ledger["paying_customers"].status == EvidenceStatus.MISSING
    assert "q_clients" in state.asked_question_ids
    # The engine moves on rather than re-asking the same question.
    assert state.current_question_id != "q_clients"


def test_engine_terminates_diagnostic_ready() -> None:
    # Everything confirmed -> no question exceeds the confidence threshold.
    confirmed = {f: _cell(True) for q in QUESTIONS_BY_ID.values() for f in
                 [s.name for s in q.extract_fields]}
    answers = {qid: {"extracted": confirmed} for qid in QUESTIONS_BY_ID}
    engine = make_engine(answers)
    state = drive(engine, engine.start_session(), max_turns=40)
    assert state.completed is True


# --- Amira fixture (the canonical case) ---


def test_amira_case_caps_below_s4() -> None:
    """Amira declares S5, has a prototype + informal status, no invoices.

    Expected: the traction evidence probe fires, invoices_with_vat stays MISSING,
    and the ledger leaves the frontier at S3 — a downstream classifier reading
    this ledger would cap at S3. The intake engine produces the ledger, never the
    stage.
    """

    answers = {
        "q_declared_stage": {"extracted": {"declared_stage": _cell("S5")}},
        "q_idea": {"extracted": {"has_prototype": _cell(True),
                                 "founding_date": _cell("2021-06-01")}},
        "q_problem_validation": {"extracted": {"problem_validated": _cell(True),
                                               "documented_interviews": _cell(8)}},
        "q_clients": {"extracted": {"paying_customers": _cell(3),
                                    "claims_traction": _cell(True),
                                    "recurring_revenue": _cell(False, "CONFIRMED")}},
        "q_legal_entity": {"extracted": {"has_legal_entity": _cell(True),
                                         "legal_form": _cell("ENTREPRISE_INDIVIDUELLE"),
                                         "formalization_status": _cell("in_progress")}},
        "q_team": {"extracted": {"team_size": _cell(2)}},
        # No invoices: both the phase question and the probe return MISSING.
        "q_invoices": {"extracted": {"invoices_with_vat": {"value": None, "status": "MISSING"}}},
        "probe_traction_evidence": {
            "extracted": {"invoices_with_vat": {"value": None, "status": "MISSING"}}
        },
    }
    engine = make_engine(answers)
    state = drive(engine, engine.start_session(), max_turns=40)

    # The traction evidence probe fired on the unbacked claim.
    assert "rule_traction_evidence" in state.fired_probes
    # Invoices with VAT were never confirmed.
    assert state.ledger["invoices_with_vat"].status == EvidenceStatus.MISSING
    # declared self-assessment is preserved but isolated.
    assert state.declared_stage == "S5"
    # Frontier caps at S3: S4 needs SARL/SUARL + invoices_with_vat, which are absent.
    assert frontier_stage(state) is EvidenceStage.S3


@pytest.mark.parametrize(
    "kind", [ProbeKind.EVIDENCE, ProbeKind.SECTOR, ProbeKind.STAGE_SKIP]
)
def test_probe_kinds_exist_in_bank(kind: ProbeKind) -> None:
    from shared.intake.question_bank import PROBE_RULES

    assert any(rule.kind is kind for rule in PROBE_RULES)
