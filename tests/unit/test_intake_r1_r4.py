"""Regression tests for R1-R4. Each would FAIL against the pre-R1-R4 code.

The LLM stays mocked/scripted so these remain deterministic (R1 is verified at the
*provider-selection* level here; the live network path is exercised by the manual
verification script, not the test suite).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from shared.contracts.enums import EvidenceStage, EvidenceStatus, MaturityStage
from shared.intake import Extractor, InMemorySessionStore, IntakeEngine, build_extractor
from shared.intake.contracts import IntakeState
from shared.intake.missing_info import frontier_progress
from shared.intake.question_bank import QUESTIONS_BY_ID
from shared.llm import MockLLMProvider, OpenAICompatibleProvider


class ScriptedLLM:
    def __init__(self, answers: dict[str, dict[str, Any]]) -> None:
        self._answers = answers

    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        return json.dumps(self._answers.get(context["question_id"], {"extracted": {}}))


def _cell(value: Any, status: str = "CONFIRMED") -> dict[str, Any]:
    return {"value": value, "status": status}


def make_engine(answers: dict[str, dict[str, Any]]) -> IntakeEngine:
    return IntakeEngine(
        extractor=Extractor(ScriptedLLM(answers)), session_store=InMemorySessionStore()
    )


# --- R1: openrouter selects the real provider in the default path ---


def test_r1_build_extractor_selects_openrouter_provider(monkeypatch) -> None:
    """Pre-R1, build_extractor only matched 'openai_compatible' -> openrouter fell
    back to the prose MockLLMProvider and silently degraded."""

    import shared.intake as intake_pkg

    class FakeSettings:
        llm_provider = "openrouter"
        openai_compatible_base_url = "https://openrouter.ai/api/v1"
        openai_compatible_api_key = "sk-test"
        openai_compatible_model = "qwen/qwen3-next-80b-a3b-instruct:free"

    monkeypatch.setattr(intake_pkg, "get_settings", lambda: FakeSettings())
    extractor = build_extractor()
    assert isinstance(extractor._provider, OpenAICompatibleProvider)
    assert extractor._provider.model.startswith("qwen/")


def test_r1_mock_fallback_degrades_and_is_not_silent(caplog) -> None:
    """A prose (non-JSON) provider must degrade to all-MISSING AND log a WARNING."""

    import logging

    with caplog.at_level(logging.WARNING, logger="intake.extractor"):
        result = asyncio.run(
            Extractor(MockLLMProvider()).extract(QUESTIONS_BY_ID["q_clients"], "3 clients", "fr")
        )
    assert result.degraded is True
    assert result.extracted == {}
    assert any("DEGRADED" in rec.message for rec in caplog.records)


# --- R2: runtime ledger -> diagnosis handoff ---


def test_r2_build_diagnosis_runs_predictor_and_scorer() -> None:
    from shared.domain.diagnosis import build_diagnosis

    answers = {
        "q_declared_stage": {"extracted": {"declared_stage": _cell("S5")}},
        "q_problem_validation": {
            "extracted": {"problem_validated": _cell(True), "documented_interviews": _cell(8)}
        },
        "q_legal_entity": {
            "extracted": {
                "has_legal_entity": _cell(True),
                "legal_form": _cell("ENTREPRISE_INDIVIDUELLE"),
            }
        },
        "q_clients": {"extracted": {"paying_customers": _cell(3), "claims_traction": _cell(True)}},
    }
    engine = make_engine(answers)
    state = engine.start_session()
    for qid in ("q_declared_stage", "q_problem_validation", "q_legal_entity", "q_clients"):
        asyncio.run(engine.process_answer(state.session_id, "x", qid))
    state = engine.get_state(state.session_id)
    assert state is not None

    diag = build_diagnosis(state)
    # Stage is produced by the downstream predictor, never by the engine.
    assert diag.diagnosis.diagnosed_stage in set(MaturityStage)
    assert 0.0 <= diag.diagnosis.confidence <= 1.0
    # The ledger itself is returned (it must leave the intake service now).
    assert "problem_validated" in diag.ledger
    assert len(diag.scores.scores) == 5
    # Declared self-assessment stays isolated and surfaced separately.
    assert diag.diagnosis.declared_stage == MaturityStage.LAUNCH_PLANNING  # S5 crosswalk


# --- R3: the two fundamental fields are now askable and reach CONFIRMED ---


def test_r3_revenue_model_and_innovation_are_askable_and_confirmable() -> None:
    targets = {q.id: q.targets for q in QUESTIONS_BY_ID.values()}
    assert any("innovation_level" in t for t in targets.values())
    assert any("revenue_model_clarity" in t for t in targets.values())

    answers = {
        "q_innovation": {"extracted": {"innovation_level": _cell("high")}},
        "q_revenue_model": {"extracted": {"revenue_model_clarity": _cell("clear")}},
    }
    engine = make_engine(answers)
    state = engine.start_session()
    asyncio.run(engine.process_answer(state.session_id, "rupture", "q_innovation"))
    state = asyncio.run(
        engine.process_answer(state.session_id, "abonnement testé", "q_revenue_model")
    )
    assert state.ledger["innovation_level"].status is EvidenceStatus.CONFIRMED
    assert state.ledger["revenue_model_clarity"].status is EvidenceStatus.CONFIRMED
    # And they feed the scorer as 0-100 ints via the diagnosis bridge.
    from shared.domain.diagnosis import project_profile_from_state

    profile = project_profile_from_state(state)
    assert profile.innovation_level == 80
    assert profile.revenue_model_clarity == 80


# --- R4: frontier-relative progress, no confirmed/13 ---


def test_r4_progress_is_frontier_relative() -> None:
    # Fresh session: frontier S1, progress measured toward S2's gates only.
    progress = frontier_progress(IntakeState())
    assert progress.frontier_stage is EvidenceStage.S1
    assert progress.next_stage is EvidenceStage.S2
    assert progress.gates_total == 2  # problem_validated + documented_interviews (NOT 13)
    assert progress.gates_satisfied == 0
    assert progress.percent_to_next == 0.0


def test_r4_progress_advances_with_frontier() -> None:
    answers = {
        "q_problem_validation": {
            "extracted": {"problem_validated": _cell(True), "documented_interviews": _cell(6)}
        }
    }
    engine = make_engine(answers)
    state = engine.start_session()
    state = asyncio.run(
        engine.process_answer(state.session_id, "validé, 6 entretiens", "q_problem_validation")
    )
    progress = frontier_progress(state)
    # S2 gates satisfied -> frontier S2, now measuring distance to S3.
    assert progress.frontier_stage is EvidenceStage.S2
    assert progress.next_stage is EvidenceStage.S3
    assert progress.gates_total == 3  # has_prototype, has_legal_entity, team_size


def test_r4_percent_complete_symbol_is_removed() -> None:
    import shared.intake.question_selector as selector

    assert not hasattr(selector, "percent_complete")
