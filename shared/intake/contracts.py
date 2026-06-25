"""Pydantic contracts owned by the Adaptive Intake Engine.

These models are the shared wire/persistence contracts for the engine. The
``evidence_ledger`` (``LedgerEntry`` keyed by field) is the cross-module
contract that downstream consumers (maturity, scoring) read. The engine never
assigns a stage or a score.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from shared.contracts.enums import (
    EvidenceStage,
    EvidenceStatus,
    IntakePhase,
    MissingKind,
    ProbeKind,
    QuestionType,
)
from shared.contracts.schemas import CompositeScores, MaturityPrediction, Question


class IntakeModel(BaseModel):
    """Base for intake contracts.

    Unlike ``ContractModel`` it keeps enum *members* (no ``use_enum_values``) so
    identity comparisons (``rule.kind is ProbeKind.EVIDENCE``) stay correct;
    enums still serialize to their string values via ``model_dump_json``.
    """

    model_config = ConfigDict(extra="forbid")

# --- Condition language (declarative, shared by probes / preconditions / contradictions) ---

ConditionOp = Literal[
    "eq", "ne", "gt", "gte", "lt", "lte", "present", "absent", "truthy", "falsy", "in", "status_in"
]


class Condition(IntakeModel):
    """A single declarative predicate over a profile value or a ledger status."""

    field: str
    op: ConditionOp = "truthy"
    value: Any = None
    # ``value`` tests the profile field; ``status`` tests the ledger entry status.
    on: Literal["value", "status"] = "value"


def _confidence_for_status(status: EvidenceStatus | str | None) -> float:
    mapping = {
        EvidenceStatus.CONFIRMED: 1.0,
        EvidenceStatus.UNVERIFIED: 0.5,
        EvidenceStatus.CONTRADICTED: 0.3,
        EvidenceStatus.MISSING: 0.0,
    }
    if status is None:
        return 0.0
    return mapping.get(EvidenceStatus(status), 0.0)


def evaluate_condition(
    condition: Condition,
    profile: dict[str, Any],
    ledger: dict[str, LedgerEntry],
) -> bool:
    """Pure evaluator. No side effects, no LLM — keeps selection deterministic."""

    if condition.on == "status":
        entry = ledger.get(condition.field)
        status = entry.status if entry else EvidenceStatus.MISSING
        if condition.op == "status_in":
            wanted = condition.value or []
            return EvidenceStatus(status) in {EvidenceStatus(item) for item in wanted}
        if condition.op == "eq":
            return EvidenceStatus(status) == EvidenceStatus(condition.value)
        if condition.op == "ne":
            return EvidenceStatus(status) != EvidenceStatus(condition.value)
        raise ValueError(f"Unsupported status op: {condition.op}")

    actual = profile.get(condition.field)
    op = condition.op
    if op == "present":
        return actual is not None and actual != [] and actual != ""
    if op == "absent":
        return actual is None or actual == [] or actual == ""
    if op == "truthy":
        return bool(actual)
    if op == "falsy":
        return not bool(actual)
    if op == "in":
        return actual in (condition.value or [])
    if actual is None:
        return False
    if op == "eq":
        return bool(actual == condition.value)
    if op == "ne":
        return bool(actual != condition.value)
    if op == "gt":
        return bool(actual > condition.value)
    if op == "gte":
        return bool(actual >= condition.value)
    if op == "lt":
        return bool(actual < condition.value)
    if op == "lte":
        return bool(actual <= condition.value)
    raise ValueError(f"Unsupported value op: {op}")


# --- Questionnaire ---


class FieldSpec(IntakeModel):
    """One field of a question's *scoped* extraction schema.

    The extractor is handed only these fields for the current question, so the
    LLM cannot invent fields (hard invariant #2).
    """

    name: str
    type: Literal["text", "boolean", "integer", "number", "enum", "date"] = "text"
    description: dict[str, str] = Field(default_factory=dict)  # fr / ar hints for the LLM
    options: list[str] = Field(default_factory=list)


class IntakeQuestion(IntakeModel):
    id: str
    phase: IntakePhase
    text: dict[str, str]  # {"fr": ..., "ar": ...}
    targets: list[str] = Field(default_factory=list)  # evidence fields this informs
    extract_fields: list[FieldSpec] = Field(default_factory=list)
    preconditions: list[Condition] = Field(default_factory=list)  # branching gates
    is_probe: bool = False  # probe questions are queued, not freely selected
    captures_declared_stage: bool = False  # the single isolated self-assessment

    def render(self, lang: str) -> Question:
        """Project onto the shared ``Question`` contract for the API/frontend."""

        options = sorted({opt for spec in self.extract_fields for opt in spec.options})
        return Question(
            id=self.id,
            code=self.id,
            text=self.text,
            type=QuestionType.TEXT,
            tags=[self.phase.value],
            options=options,
        )


# --- Probes ---


class ProbeRule(IntakeModel):
    id: str
    kind: ProbeKind
    trigger: list[Condition] = Field(default_factory=list)  # ANDed together
    ask: str | None = None  # EVIDENCE: probe question id to push
    inject: list[str] = Field(default_factory=list)  # SECTOR: question ids to enable
    mark_inferred: list[str] = Field(default_factory=list)  # STAGE_SKIP: question ids to skip
    # STAGE_SKIP: fields proven by inference
    confirm_fields: list[str] = Field(default_factory=list)
    fire_once: bool = True


# --- Contradiction rules (Tunisian regulatory coherence) ---


class ContradictionRule(IntakeModel):
    id: str
    when: list[Condition] = Field(default_factory=list)  # ANDed
    contradicted_field: str  # field flagged CONTRADICTED (never silently averaged)
    clarification_probe: str | None = None  # probe id to push for clarification
    reason: dict[str, str] = Field(default_factory=dict)  # fr / ar explanation


# --- Ledger & state ---


class LedgerEntry(IntakeModel):
    field: str
    value: Any = None
    status: EvidenceStatus = EvidenceStatus.MISSING
    source_answer_id: str | None = None
    note: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def confidence(self) -> float:
        return _confidence_for_status(self.status)


class AnswerRecord(IntakeModel):
    answer_id: str = Field(default_factory=lambda: uuid4().hex)
    question_id: str
    raw_answer: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MissingItem(IntakeModel):
    field: str
    kind: MissingKind
    value: float = 0.0  # information value (higher = ask sooner)
    gates_next_stage: bool = False
    reason: str = ""


class IntakeState(IntakeModel):
    session_id: UUID = Field(default_factory=uuid4)
    project_id: UUID = Field(default_factory=uuid4)
    lang: str = "fr"
    phase: IntakePhase = IntakePhase.FOUNDATION
    profile: dict[str, Any] = Field(default_factory=dict)
    ledger: dict[str, LedgerEntry] = Field(default_factory=dict)
    # declared_stage is collected once, kept isolated; never feeds extraction/selection.
    declared_stage: str | None = None
    # Tracks the inline q_declared_stage lifecycle (drives its one-time selection
    # boost). Deliberately NOT set by PML, so an injected PML never changes which
    # question is selected (the isolation invariant).
    declared_stage_captured: bool = False
    # Provenance of declared_stage: "pml" (Classification Service, authoritative) or
    # "inline" (our q_declared_stage, fallback). PML wins when both exist.
    declared_stage_source: str | None = None
    # Opaque PML transcript kept for perception-layer context ONLY; never fed to the
    # extractor and never written into the evidence ledger.
    pml_transcript: list[dict[str, Any]] = Field(default_factory=list)
    founding_date: str | None = None  # stored early (temporal severity hook)
    asked_question_ids: list[str] = Field(default_factory=list)
    answered_by_inference: list[str] = Field(default_factory=list)
    enabled_probe_questions: list[str] = Field(default_factory=list)  # SECTOR-injected
    pending_probes: list[str] = Field(default_factory=list)  # probe question ids queued
    fired_probes: list[str] = Field(default_factory=list)  # fire_once tracking
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    answers: list[AnswerRecord] = Field(default_factory=list)
    current_question_id: str | None = None
    completed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- API DTOs ---


class ExtractionResult(IntakeModel):
    extracted: dict[str, Any] = Field(default_factory=dict)
    evidence_status: dict[str, EvidenceStatus] = Field(default_factory=dict)
    unprompted_signals: dict[str, Any] = Field(default_factory=dict)
    # Observability: True when the LLM output could not be parsed as JSON and the
    # turn fell back to all-MISSING (so callers can log/alert without guessing).
    degraded: bool = False


class SessionStartResponse(IntakeModel):
    session_id: UUID
    first_question: Question | None = None


class AnswerResponse(IntakeModel):
    next_question: Question | None = None
    diagnostic_ready: bool = False
    fired_probes: list[str] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)


class DiagnosisResponse(IntakeModel):
    """Runtime handoff result: the intake ledger fed to the EXISTING downstream
    maturity predictor and scorer. The engine never assigns the stage (§9.1); the
    stage here is produced only by the downstream consumers.
    """

    session_id: UUID
    completed: bool
    frontier_stage: EvidenceStage
    declared_stage: str | None = None
    diagnosis: MaturityPrediction
    scores: CompositeScores
    ledger: dict[str, LedgerEntry] = Field(default_factory=dict)


class StateResponse(IntakeModel):
    phase: IntakePhase
    # Frontier-relative progress (invariant §9.5): distance to the NEXT stage, not
    # answered/total over a fixed field set.
    frontier_stage: EvidenceStage
    next_stage: EvidenceStage | None = None
    gates_satisfied: int = 0
    gates_total: int = 0
    percent_to_next: float = Field(default=0.0, ge=0, le=100)
    declared_stage: str | None = None
    completed: bool = False
