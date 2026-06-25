from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel

from shared.contracts.enums import EvidenceStage, EvidenceStatus, GapLevel, MaturityStage
from shared.contracts.schemas import EvidenceItem, MaturityPrediction, ProjectProfile
from shared.domain.utils import STAGE_ORDER, clamp, stage
from shared.intake.requirements import (
    EVIDENCE_TO_MATURITY,
    contradicted_gates,
    frontier_stage,
    gate_specs,
    next_stage,
    status_of,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from shared.intake.contracts import LedgerEntry


class RuleBasedMaturityPredictor:
    name = "rule_based_maturity"
    version = "rules-v0.1.0"

    def predict(self, profile: ProjectProfile) -> MaturityPrediction:
        evidence: list[EvidenceItem] = []
        triggered_rules: list[str] = []

        paying_customers = profile.paying_customers or 0
        interviews = profile.documented_interviews or 0
        has_mvp = bool(profile.has_mvp)
        has_revenue = bool(profile.has_revenue or (profile.monthly_revenue or 0) > 0)
        evidence_count = len(profile.market_validation_evidence)

        if paying_customers >= 5 or (has_revenue and (profile.monthly_revenue or 0) >= 1000):
            diagnosed = MaturityStage.GROWTH
            triggered_rules.append("MATURITY-GROWTH-001")
            evidence.append(
                EvidenceItem(
                    field="paying_customers",
                    value=paying_customers,
                    impact="positive",
                    rule_id="MATURITY-GROWTH-001",
                )
            )
        elif has_revenue or paying_customers >= 1:
            diagnosed = MaturityStage.FUNDRAISING
            triggered_rules.append("MATURITY-FUND-002")
            evidence.append(
                EvidenceItem(
                    field="has_revenue",
                    value=has_revenue,
                    impact="positive",
                    rule_id="MATURITY-FUND-002",
                )
            )
        elif has_mvp and (paying_customers == 0 or interviews < 10 or evidence_count < 2):
            diagnosed = MaturityStage.MARKET_VALIDATION
            triggered_rules.extend(["MATURITY-VAL-003", "MATURITY-FUND-001"])
            evidence.extend(
                [
                    EvidenceItem(
                        field="paying_customers",
                        value=paying_customers,
                        impact="negative",
                        rule_id="MATURITY-VAL-003",
                    ),
                    EvidenceItem(
                        field="market_validation_evidence",
                        value="weak" if evidence_count < 2 else "partial",
                        impact="negative",
                        rule_id="MATURITY-FUND-001",
                    ),
                ]
            )
        elif profile.legal_form and profile.formalization_status == "formalized":
            diagnosed = MaturityStage.STRUCTURATION
            triggered_rules.append("MATURITY-STRUCT-001")
            evidence.append(
                EvidenceItem(
                    field="formalization_status",
                    value="formalized",
                    impact="positive",
                    rule_id="MATURITY-STRUCT-001",
                )
            )
        else:
            diagnosed = MaturityStage.IDEATION
            triggered_rules.append("MATURITY-IDEA-001")
            evidence.append(
                EvidenceItem(
                    field="has_mvp",
                    value=profile.has_mvp,
                    impact="negative",
                    rule_id="MATURITY-IDEA-001",
                )
            )

        declared = stage(profile.declared_stage)
        confidence = self._confidence(profile, diagnosed)
        return MaturityPrediction(
            diagnosed_stage=diagnosed,
            declared_stage=declared,
            gap_level=self._gap_level(declared, diagnosed),
            confidence=confidence,
            evidence=evidence,
            triggered_rules=triggered_rules,
            model_version=self.version,
        )

    def _gap_level(self, declared: MaturityStage, diagnosed: MaturityStage) -> GapLevel:
        distance = abs(STAGE_ORDER[declared] - STAGE_ORDER[diagnosed])
        if distance == 0:
            return GapLevel.NONE
        if distance == 1:
            return GapLevel.MEDIUM
        return GapLevel.HIGH

    def _confidence(self, profile: ProjectProfile, diagnosed: MaturityStage) -> float:
        required = [
            profile.has_mvp,
            profile.paying_customers,
            profile.market_validation_evidence,
            profile.declared_stage,
            profile.business_type,
        ]
        missing = sum(1 for value in required if value in (None, [], ""))
        base = 0.84 if diagnosed in {MaturityStage.MARKET_VALIDATION, MaturityStage.GROWTH} else 0.74
        return max(0.35, round(base - missing * 0.08, 2))


def _declared_to_maturity(value: str | None) -> MaturityStage:
    """Map the isolated self-assessment (S1-S6 or a MaturityStage name) to a stage."""

    if not value:
        return MaturityStage.IDEATION
    try:
        return EVIDENCE_TO_MATURITY[EvidenceStage(value)]
    except ValueError:
        try:
            return MaturityStage(value)
        except ValueError:
            return MaturityStage.IDEATION


def _company_age_months(founding_date: str | None) -> int | None:
    if not founding_date:
        return None
    try:
        started = date.fromisoformat(founding_date[:10])
    except ValueError:
        return None
    today = date.today()
    return (today.year - started.year) * 12 + (today.month - started.month)


class LedgerMaturityPredictor:
    """Diagnose a maturity stage from the intake evidence ledger.

    Reads the shared evidence ledger + requirements registry (never the intake
    engine itself). CONFIRMED evidence advances the frontier; UNVERIFIED and
    MISSING gates of the next stage degrade confidence; CONTRADICTED gates are
    surfaced as blockers. The diagnosis is the document-gated frontier mapped to
    ``MaturityStage`` — declared intent never lifts it.
    """

    name = "ledger_maturity"
    version = "ledger-rules-v0.1.0"

    def predict(
        self,
        ledger: Mapping[str, LedgerEntry],
        declared_stage: str | None = None,
        founding_date: str | None = None,
    ) -> MaturityPrediction:
        evidence_stage = frontier_stage(ledger)
        diagnosed = EVIDENCE_TO_MATURITY[evidence_stage]
        declared = _declared_to_maturity(declared_stage)

        evidence: list[EvidenceItem] = []
        triggered_rules: list[str] = [f"LEDGER-FRONTIER-{evidence_stage.value}"]

        for spec in gate_specs(evidence_stage):
            entry = ledger.get(spec.field)
            evidence.append(
                EvidenceItem(
                    field=spec.field,
                    value=entry.value if entry else True,
                    impact="positive",
                    rule_id=f"LEDGER-GATE-{evidence_stage.value}",
                )
            )

        unverified: list[str] = []
        missing: list[str] = []
        target = next_stage(evidence_stage)
        if target is not None:
            for spec in gate_specs(target):
                entry = ledger.get(spec.field)
                field_status = status_of(ledger, spec.field)
                if field_status is EvidenceStatus.UNVERIFIED:
                    unverified.append(spec.field)
                    evidence.append(
                        EvidenceItem(
                            field=spec.field,
                            value="unverified",
                            impact="negative",
                            rule_id="LEDGER-UNVERIFIED",
                        )
                    )
                elif field_status is EvidenceStatus.MISSING:
                    missing.append(spec.field)
                elif (
                    field_status is EvidenceStatus.CONFIRMED
                    and entry is not None
                    and not spec.gate.satisfied(entry.value)
                ):
                    # Confirmed but insufficient (e.g. sole proprietorship at the S4
                    # legal-form gate): explains why the next stage is not reached.
                    triggered_rules.append("LEDGER-STRUCTURAL-GAP")
                    evidence.append(
                        EvidenceItem(
                            field=spec.field,
                            value=entry.value,
                            impact="negative",
                            rule_id="LEDGER-STRUCTURAL-GAP",
                        )
                    )

        contradicted = contradicted_gates(ledger)
        for field in contradicted:
            triggered_rules.append("LEDGER-CONTRADICTION")
            evidence.append(
                EvidenceItem(
                    field=field,
                    value="contradicted",
                    impact="negative",
                    rule_id="LEDGER-CONTRADICTION",
                )
            )

        confidence = clamp(
            0.85 - 0.07 * len(unverified) - 0.05 * len(missing) - (0.1 if contradicted else 0.0),
            0.3,
            0.95,
        )

        # Temporal severity hook: a very young company over-claiming its stage.
        age_months = _company_age_months(founding_date)
        if age_months is not None:
            evidence.append(
                EvidenceItem(
                    field="founding_date",
                    value=age_months,
                    impact="context",
                    rule_id="LEDGER-TEMPORAL",
                )
            )
            gap_distance = STAGE_ORDER[declared] - STAGE_ORDER[diagnosed]
            if age_months < 6 and gap_distance >= 2:
                triggered_rules.append("LEDGER-TEMPORAL-YOUNG-OVERCLAIM")
                confidence = clamp(confidence - 0.05, 0.3, 0.95)

        return MaturityPrediction(
            diagnosed_stage=diagnosed,
            declared_stage=declared,
            gap_level=self._gap_level(declared, diagnosed),
            confidence=round(confidence, 2),
            evidence=evidence,
            triggered_rules=triggered_rules,
            model_version=self.version,
        )

    def _gap_level(self, declared: MaturityStage, diagnosed: MaturityStage) -> GapLevel:
        distance = abs(STAGE_ORDER[declared] - STAGE_ORDER[diagnosed])
        if distance == 0:
            return GapLevel.NONE
        if distance == 1:
            return GapLevel.MEDIUM
        return GapLevel.HIGH


class SklearnMaturityPredictor:
    name = "sklearn_maturity"
    version = "sklearn-v0.1.0"

    def __init__(self) -> None:
        self.fallback = RuleBasedMaturityPredictor()

    def load(self) -> None:
        return None

    def predict(self, profile: ProjectProfile) -> MaturityPrediction:
        prediction = self.fallback.predict(profile)
        return prediction.model_copy(update={"model_version": self.version})

    def predict_model(self, payload: BaseModel) -> BaseModel:
        if not isinstance(payload, ProjectProfile):
            raise TypeError("SklearnMaturityPredictor expects a ProjectProfile payload")
        return self.predict(payload)
