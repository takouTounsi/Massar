"""Extraction quality eval harness.

Runs the extractor over annotated AR/FR answers and reports field-level
precision/recall plus per-field status accuracy, so prompt/provider changes can
be measured rather than guessed. With the mock provider scores are ~0; point it
at a real provider to get a meaningful signal. The metric computation itself is
covered by a deterministic test using a scripted (imperfect) provider.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.contracts.enums import EvidenceStatus
from shared.intake.extractor import Extractor
from shared.intake.question_bank import QUESTIONS_BY_ID

DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "intake" / "extraction_eval.json"


@dataclass(frozen=True)
class EvalCase:
    question_id: str
    lang: str
    raw_answer: str
    expected: dict[str, dict[str, Any]]  # field -> {value, status}


@dataclass(frozen=True)
class EvalMetrics:
    cases: int
    precision: float  # of predicted (non-MISSING) fields, fraction value-correct
    recall: float  # of expected (non-MISSING) fields, fraction value-correct
    status_accuracy: float  # fraction of expected fields with the right status

    def as_dict(self) -> dict[str, float | int]:
        return {
            "cases": self.cases,
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "status_accuracy": round(self.status_accuracy, 3),
        }


def load_cases(path: Path | None = None) -> list[EvalCase]:
    raw = json.loads((path or DATASET_PATH).read_text(encoding="utf-8"))
    return [EvalCase(**item) for item in raw]


async def evaluate_extractor(extractor: Extractor, cases: list[EvalCase]) -> EvalMetrics:
    predicted_total = 0
    predicted_correct = 0
    expected_total = 0
    expected_correct = 0
    status_total = 0
    status_correct = 0

    for case in cases:
        question = QUESTIONS_BY_ID[case.question_id]
        result = await extractor.extract(question, case.raw_answer, case.lang)

        expected_present = {
            field: cell
            for field, cell in case.expected.items()
            if EvidenceStatus(cell["status"]) is not EvidenceStatus.MISSING
        }
        predicted_present = result.extracted

        predicted_total += len(predicted_present)
        expected_total += len(expected_present)

        for field, value in predicted_present.items():
            if field in expected_present and expected_present[field]["value"] == value:
                predicted_correct += 1
        for field, cell in expected_present.items():
            if field in predicted_present and predicted_present[field] == cell["value"]:
                expected_correct += 1

        for field, cell in case.expected.items():
            status_total += 1
            predicted_status = result.evidence_status.get(field, EvidenceStatus.MISSING)
            if EvidenceStatus(predicted_status) is EvidenceStatus(cell["status"]):
                status_correct += 1

    return EvalMetrics(
        cases=len(cases),
        precision=predicted_correct / predicted_total if predicted_total else 0.0,
        recall=expected_correct / expected_total if expected_total else 0.0,
        status_accuracy=status_correct / status_total if status_total else 0.0,
    )
