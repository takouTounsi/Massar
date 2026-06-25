"""Shared requirements registry (data, not logic).

Maps each evidence field to ``{stage_gates, scoring_criteria, fundamental}`` plus
a declarative gate predicate. The intake engine reads this for frontier-relative
missing-info detection WITHOUT importing the classifier/scorer; the
classifier/scorer can read the very same registry. Nothing here decides a stage
or a score — it only states which evidence each gate needs.

Stages are the document-evidence-gated S1-S6 taxonomy (``EvidenceStage``).
See docs/intake-engine.md for the crosswalk to ``MaturityStage``.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import TYPE_CHECKING, Any, Literal

from shared.contracts.enums import EvidenceStage, EvidenceStatus, MaturityStage

if TYPE_CHECKING:
    from collections.abc import Mapping

    from shared.intake.contracts import LedgerEntry

# Crosswalk from the document-gated S1-S6 taxonomy to the project-wide
# ``MaturityStage`` so downstream consumers (classifier) can read the same gates.
EVIDENCE_TO_MATURITY: dict[EvidenceStage, MaturityStage] = {
    EvidenceStage.S1: MaturityStage.IDEATION,
    EvidenceStage.S2: MaturityStage.MARKET_VALIDATION,
    EvidenceStage.S3: MaturityStage.STRUCTURATION,
    EvidenceStage.S4: MaturityStage.FUNDRAISING,
    EvidenceStage.S5: MaturityStage.LAUNCH_PLANNING,
    EvidenceStage.S6: MaturityStage.GROWTH,
}

STAGE_ORDER: dict[EvidenceStage, int] = {
    EvidenceStage.S1: 1,
    EvidenceStage.S2: 2,
    EvidenceStage.S3: 3,
    EvidenceStage.S4: 4,
    EvidenceStage.S5: 5,
    EvidenceStage.S6: 6,
}


@dataclass(frozen=True)
class GatePredicate:
    """How a raw field value is tested for gate satisfaction."""

    kind: Literal["truthy", "min", "in"] = "truthy"
    value: Any = None

    def satisfied(self, raw: Any) -> bool:
        if raw is None:
            return False
        if self.kind == "truthy":
            return bool(raw)
        if self.kind == "min":
            try:
                return float(raw) >= float(self.value)
            except (TypeError, ValueError):
                return False
        return raw in (self.value or [])  # kind == "in"

    def is_negative(self, raw: Any) -> bool:
        """Value is present but fails the gate -> a structural gap, not a question."""

        if raw is None or raw == "" or raw == []:
            return False
        return not self.satisfied(raw)


@dataclass(frozen=True)
class RequirementSpec:
    field: str
    stage_gates: tuple[EvidenceStage, ...] = ()
    scoring_criteria: tuple[str, ...] = ()
    fundamental: bool = False
    gate: GatePredicate = dc_field(default_factory=GatePredicate)


# The registry. Document-gated artifacts (RNE / TVA / CNSS / factures) gate the
# higher stages; declared intent never gates anything.
REQUIREMENTS: dict[str, RequirementSpec] = {
    spec.field: spec
    for spec in (
        # S2 — problem validated / informal
        RequirementSpec(
            field="problem_validated",
            stage_gates=(EvidenceStage.S2,),
            scoring_criteria=("market",),
        ),
        RequirementSpec(
            field="documented_interviews",
            stage_gates=(EvidenceStage.S2,),
            scoring_criteria=("market",),
            gate=GatePredicate(kind="min", value=1),
        ),
        # S3 — prototype + entity started (RNE)
        RequirementSpec(
            field="has_prototype",
            stage_gates=(EvidenceStage.S3,),
            scoring_criteria=("innovation",),
        ),
        RequirementSpec(
            field="has_legal_entity",  # RNE registration started
            stage_gates=(EvidenceStage.S3,),
        ),
        RequirementSpec(
            field="team_size",
            stage_gates=(EvidenceStage.S3,),
            scoring_criteria=("scalability",),
            gate=GatePredicate(kind="min", value=2),
        ),
        # S4 — real commercial traction (factures w/ TVA, SARL/SUARL)
        RequirementSpec(
            field="legal_form",
            stage_gates=(EvidenceStage.S4,),
            gate=GatePredicate(kind="in", value=["SARL", "SUARL", "SA"]),
        ),
        RequirementSpec(
            field="invoices_with_vat",  # factures with TVA
            stage_gates=(EvidenceStage.S4,),
            scoring_criteria=("commercial_offer", "market"),
            fundamental=True,
        ),
        RequirementSpec(
            field="paying_customers",
            stage_gates=(EvidenceStage.S4,),
            scoring_criteria=("market", "commercial_offer"),
            fundamental=True,
            gate=GatePredicate(kind="min", value=1),
        ),
        # S5 — proven model + fiscal compliance (TVA filings, CNSS)
        RequirementSpec(
            field="has_tva",
            stage_gates=(EvidenceStage.S5,),
        ),
        RequirementSpec(
            field="has_cnss",
            stage_gates=(EvidenceStage.S5,),
        ),
        RequirementSpec(
            field="recurring_revenue",
            stage_gates=(EvidenceStage.S5,),
            scoring_criteria=("commercial_offer",),
        ),
        # S6 — investment-ready / scaling
        RequirementSpec(
            field="monthly_revenue",
            stage_gates=(EvidenceStage.S6,),
            scoring_criteria=("scalability",),
            gate=GatePredicate(kind="min", value=1),
        ),
        RequirementSpec(
            field="process_automation_level",
            stage_gates=(EvidenceStage.S6,),
            scoring_criteria=("scalability",),
        ),
        # Fundamental scoring fields that do not gate a stage but always matter.
        RequirementSpec(
            field="revenue_model_clarity",
            scoring_criteria=("commercial_offer",),
            fundamental=True,
        ),
        RequirementSpec(
            field="innovation_level",
            scoring_criteria=("innovation",),
            fundamental=True,
        ),
        RequirementSpec(
            field="market_size_known",
            scoring_criteria=("market",),
        ),
    )
}


def gate_specs(stage: EvidenceStage) -> list[RequirementSpec]:
    """Evidence fields that gate entry into ``stage``."""

    return [spec for spec in REQUIREMENTS.values() if stage in spec.stage_gates]


def fundamental_specs() -> list[RequirementSpec]:
    return [spec for spec in REQUIREMENTS.values() if spec.fundamental]


def next_stage(stage: EvidenceStage) -> EvidenceStage | None:
    order = STAGE_ORDER[stage]
    for candidate, candidate_order in STAGE_ORDER.items():
        if candidate_order == order + 1:
            return candidate
    return None


# --- Ledger-driven gate evaluation (shared by the engine and downstream consumers) ---


def status_of(ledger: Mapping[str, LedgerEntry], field: str) -> EvidenceStatus:
    entry = ledger.get(field)
    return EvidenceStatus(entry.status) if entry else EvidenceStatus.MISSING


def gate_satisfied(ledger: Mapping[str, LedgerEntry], spec: RequirementSpec) -> bool:
    """A gate is met only by CONFIRMED evidence whose value clears the predicate."""

    entry = ledger.get(spec.field)
    if entry is None or EvidenceStatus(entry.status) is not EvidenceStatus.CONFIRMED:
        return False
    return spec.gate.satisfied(entry.value)


def frontier_stage(ledger: Mapping[str, LedgerEntry]) -> EvidenceStage:
    """Highest contiguous stage whose gates are all satisfied (S1 is free)."""

    frontier = EvidenceStage.S1
    for stage in sorted(STAGE_ORDER, key=lambda s: STAGE_ORDER[s]):
        if stage is EvidenceStage.S1:
            continue
        if all(gate_satisfied(ledger, spec) for spec in gate_specs(stage)):
            frontier = stage
        else:
            break
    return frontier


def contradicted_gates(ledger: Mapping[str, LedgerEntry]) -> list[str]:
    """Gate fields explicitly flagged CONTRADICTED (block a clean diagnosis)."""

    return [
        spec.field
        for spec in REQUIREMENTS.values()
        if spec.stage_gates and status_of(ledger, spec.field) is EvidenceStatus.CONTRADICTED
    ]


def evidence_justification(ledger: Mapping[str, LedgerEntry], field: str) -> int:
    """ej for the scorer: 1 when CONFIRMED, else 0 (UNVERIFIED never justifies)."""

    return 1 if status_of(ledger, field) is EvidenceStatus.CONFIRMED else 0


def criteria_evidence_factor(ledger: Mapping[str, LedgerEntry], criterion: str) -> float:
    """Mean ej over the fields feeding a scoring criterion (1.0 if none on record)."""

    fields = [
        spec.field
        for spec in REQUIREMENTS.values()
        if criterion in spec.scoring_criteria and spec.field in ledger
    ]
    if not fields:
        return 1.0
    return sum(evidence_justification(ledger, f) for f in fields) / len(fields)
