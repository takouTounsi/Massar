from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from shared.contracts.schemas import (
    BlockerResult,
    CompositeScores,
    MaturityPrediction,
    ProjectProfile,
    Question,
    TenderProbeResult,
)


class VersionedModel(Protocol):
    @property
    def name(self) -> str:
        ...

    @property
    def version(self) -> str:
        ...

    def load(self) -> None:
        ...

    def predict(self, payload: BaseModel) -> BaseModel:
        ...


class MaturityPredictor(Protocol):
    def predict(self, profile: ProjectProfile) -> MaturityPrediction:
        ...


class ScoreCalculator(Protocol):
    def calculate(self, profile: ProjectProfile) -> CompositeScores:
        ...


class BlockerDetector(Protocol):
    def detect(self, profile: ProjectProfile, maturity: MaturityPrediction) -> BlockerResult:
        ...


class DiagnosticProbe(Protocol):
    def should_activate(self, profile: ProjectProfile) -> bool:
        ...

    def questions(self, profile: ProjectProfile) -> list[Question]:
        ...

    def evaluate(self, profile: ProjectProfile) -> TenderProbeResult:
        ...
