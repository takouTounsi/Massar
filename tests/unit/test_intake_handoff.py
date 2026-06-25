"""Tests for Task 1 (real, safe extraction) and Task 2 (intake -> downstream handoff).

The LLM is always mocked; everything stays deterministic.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from shared.contracts.enums import EvidenceStage, EvidenceStatus, GapLevel, MaturityStage
from shared.domain.maturity import LedgerMaturityPredictor
from shared.domain.scoring import WeightedRuleScoreCalculator
from shared.intake import Extractor, InMemorySessionStore, IntakeEngine
from shared.intake.contracts import LedgerEntry
from shared.intake.extraction_eval import EvalCase, evaluate_extractor
from shared.intake.extractor import redact_pii
from shared.intake.missing_info import frontier_stage
from shared.intake.question_bank import QUESTIONS_BY_ID
from shared.intake.requirements import (
    criteria_evidence_factor,
    evidence_justification,
)
from shared.testing import case_market_validation_gap

# --- Task 1: robust extraction ---


class FixedLLM:
    def __init__(self, text: str) -> None:
        self.text = text

    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        return self.text


class SequenceLLM:
    """Returns each queued reply in turn (to test retry behaviour)."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls = 0

    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return reply


def _extract(provider: Any, question_id: str, answer: str, **kwargs: Any):
    return asyncio.run(
        Extractor(provider, **kwargs).extract(QUESTIONS_BY_ID[question_id], answer, "fr")
    )


def test_extractor_parses_fenced_json() -> None:
    fenced = "```json\n" + json.dumps(
        {"extracted": {"paying_customers": {"value": 5, "status": "CONFIRMED"}}}
    ) + "\n```"
    result = _extract(FixedLLM(fenced), "q_clients", "five clients")
    assert result.extracted["paying_customers"] == 5
    assert result.degraded is False


def test_extractor_parses_prose_wrapped_json() -> None:
    prose = (
        "Sure! Here is the extraction:\n"
        '{"extracted": {"paying_customers": {"value": 2, "status": "CONFIRMED"}}}\n'
        "Hope this helps."
    )
    result = _extract(FixedLLM(prose), "q_clients", "two clients")
    assert result.extracted["paying_customers"] == 2
    assert result.degraded is False


def test_extractor_retries_then_succeeds() -> None:
    good = json.dumps({"extracted": {"paying_customers": {"value": 4, "status": "CONFIRMED"}}})
    provider = SequenceLLM(["not json", good])
    result = _extract(provider, "q_clients", "four", max_attempts=2)
    assert provider.calls == 2
    assert result.extracted["paying_customers"] == 4
    assert result.degraded is False


def test_extractor_degrades_after_exhausting_retries() -> None:
    provider = SequenceLLM(["garbage", "still garbage"])
    result = _extract(provider, "q_clients", "x", max_attempts=2)
    assert result.degraded is True
    assert result.extracted == {}
    assert result.evidence_status["paying_customers"] is EvidenceStatus.MISSING


def test_redact_pii() -> None:
    raw = "Contact: amira@example.com, tel +216 22 123 456, matricule fiscal 1234567"
    redacted = redact_pii(raw)
    assert "amira@example.com" not in redacted
    assert "1234567" not in redacted
    assert "[email]" in redacted and "[id]" in redacted


def test_engine_stores_redacted_answer() -> None:
    engine = IntakeEngine(
        extractor=Extractor(FixedLLM('{"extracted": {}}')),
        session_store=InMemorySessionStore(),
    )
    state = engine.start_session()
    state = asyncio.run(
        engine.process_answer(state.session_id, "mon email est amira@example.com", "q_sector")
    )
    stored = next(a for a in state.answers if a.question_id == "q_sector")
    assert "amira@example.com" not in stored.raw_answer
    assert "[email]" in stored.raw_answer


def test_extraction_eval_harness_scores_imperfect_provider() -> None:
    # One field correct, one wrong value, one status wrong -> metrics < 1.
    cases = [
        EvalCase(
            question_id="q_clients",
            lang="fr",
            raw_answer="trois clients",
            expected={
                "paying_customers": {"value": 3, "status": "CONFIRMED"},
                "recurring_revenue": {"value": True, "status": "CONFIRMED"},
            },
        )
    ]

    class HalfRightLLM:
        async def generate(self, prompt: str, context: dict[str, Any]) -> str:
            return json.dumps(
                {
                    "extracted": {
                        "paying_customers": {"value": 3, "status": "CONFIRMED"},
                        "recurring_revenue": {"value": False, "status": "CONFIRMED"},
                    }
                }
            )

    metrics = asyncio.run(evaluate_extractor(Extractor(HalfRightLLM()), cases))
    assert metrics.cases == 1
    assert metrics.recall == 0.5  # 1 of 2 expected fields value-correct
    assert 0.0 < metrics.precision <= 1.0


# --- Task 2: intake -> downstream handoff ---


def _ledger(**fields: tuple[Any, EvidenceStatus]) -> dict[str, LedgerEntry]:
    return {
        name: LedgerEntry(field=name, value=value, status=status)
        for name, (value, status) in fields.items()
    }


def _amira_ledger() -> dict[str, LedgerEntry]:
    C = EvidenceStatus.CONFIRMED
    return _ledger(
        problem_validated=(True, C),
        documented_interviews=(8, C),
        has_prototype=(True, C),
        has_legal_entity=(True, C),
        team_size=(2, C),
        legal_form=("ENTREPRISE_INDIVIDUELLE", C),  # not SARL/SUARL -> blocks S4
        paying_customers=(3, C),
        invoices_with_vat=(None, EvidenceStatus.MISSING),
    )


def test_ledger_classifier_caps_amira_at_structuration() -> None:
    prediction = LedgerMaturityPredictor().predict(_amira_ledger(), declared_stage="S5")
    assert prediction.diagnosed_stage == MaturityStage.STRUCTURATION  # S3 via crosswalk
    assert prediction.declared_stage == MaturityStage.LAUNCH_PLANNING  # S5 isolated
    assert prediction.gap_level == GapLevel.HIGH
    # The sole-proprietorship legal form is explained as why S4 is not reached.
    assert "LEDGER-STRUCTURAL-GAP" in prediction.triggered_rules


def test_ledger_classifier_confidence_degrades_with_unverified() -> None:
    C = EvidenceStatus.CONFIRMED
    strong = _ledger(problem_validated=(True, C), documented_interviews=(5, C))
    weak = _ledger(
        problem_validated=(True, C),
        documented_interviews=(5, C),
        has_prototype=(True, EvidenceStatus.UNVERIFIED),  # S3 gate only claimed
    )
    predictor = LedgerMaturityPredictor()
    assert predictor.predict(weak).confidence < predictor.predict(strong).confidence


def test_ledger_classifier_flags_contradiction() -> None:
    C = EvidenceStatus.CONFIRMED
    ledger = _ledger(
        problem_validated=(True, C),
        documented_interviews=(5, C),
        has_prototype=(True, C),
        has_legal_entity=(False, EvidenceStatus.CONTRADICTED),  # blocks S3
        team_size=(3, C),
    )
    prediction = LedgerMaturityPredictor().predict(ledger)
    assert prediction.diagnosed_stage == MaturityStage.MARKET_VALIDATION  # capped at S2
    assert "LEDGER-CONTRADICTION" in prediction.triggered_rules


def test_young_company_overclaim_lowers_confidence() -> None:
    ledger = _ledger(
        problem_validated=(True, EvidenceStatus.CONFIRMED),
        documented_interviews=(3, EvidenceStatus.CONFIRMED),
    )
    predictor = LedgerMaturityPredictor()
    baseline = predictor.predict(ledger, declared_stage="S6")
    young = predictor.predict(ledger, declared_stage="S6", founding_date="2026-05-01")
    assert young.confidence < baseline.confidence
    assert "LEDGER-TEMPORAL-YOUNG-OVERCLAIM" in young.triggered_rules


def test_engine_and_classifier_agree_on_frontier() -> None:
    # Drive a short session, then classify its ledger: same frontier stage.
    answers = {
        "q_problem_validation": {
            "extracted": {
                "problem_validated": {"value": True, "status": "CONFIRMED"},
                "documented_interviews": {"value": 6, "status": "CONFIRMED"},
            }
        }
    }

    class Scripted:
        async def generate(self, prompt: str, context: dict[str, Any]) -> str:
            return json.dumps(answers.get(context["question_id"], {"extracted": {}}))

    engine = IntakeEngine(extractor=Extractor(Scripted()), session_store=InMemorySessionStore())
    state = engine.start_session()
    state = asyncio.run(
        engine.process_answer(state.session_id, "validé, 6 entretiens", "q_problem_validation")
    )
    engine_frontier = frontier_stage(state)
    prediction = LedgerMaturityPredictor().predict(state.ledger, state.declared_stage)
    from shared.intake.requirements import EVIDENCE_TO_MATURITY

    assert engine_frontier == EvidenceStage.S2
    assert prediction.diagnosed_stage == EVIDENCE_TO_MATURITY[engine_frontier]


# --- Task 2c: evidence justification for the scorer ---


def test_evidence_justification_is_binary_on_confirmed() -> None:
    ledger = _ledger(
        paying_customers=(3, EvidenceStatus.CONFIRMED),
        invoices_with_vat=(True, EvidenceStatus.UNVERIFIED),
    )
    assert evidence_justification(ledger, "paying_customers") == 1
    assert evidence_justification(ledger, "invoices_with_vat") == 0  # claimed, not justified
    # 'market' criterion: paying_customers (ej=1) + invoices_with_vat (ej=0) -> 0.5
    assert criteria_evidence_factor(ledger, "market") == 0.5


def test_scorer_confidence_scaled_by_evidence() -> None:
    profile = case_market_validation_gap()
    calc = WeightedRuleScoreCalculator()
    base = calc.calculate(profile).by_name()["market_score"]
    # All market-feeding fields only UNVERIFIED -> ej factor 0 -> confidence collapses.
    ledger = _ledger(
        paying_customers=(0, EvidenceStatus.UNVERIFIED),
        market_size_known=(False, EvidenceStatus.UNVERIFIED),
    )
    scaled = calc.calculate_with_ledger(profile, ledger).by_name()["market_score"]
    assert scaled.value == base.value  # headline value unchanged
    assert scaled.confidence < base.confidence  # confidence degraded by weak evidence
