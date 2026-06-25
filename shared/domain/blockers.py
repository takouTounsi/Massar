from __future__ import annotations

from shared.contracts.enums import BlockerType, MaturityStage, Severity, TenderReadinessStatus
from shared.contracts.schemas import Blocker, BlockerResult, MaturityPrediction, ProjectProfile
from shared.domain.probes import TenderReadinessProbe
from shared.domain.utils import SEVERITY_ORDER, stage


class RuleBasedBlockerDetector:
    name = "rule_based_blockers"
    version = "rules-v0.1.0"

    def detect(self, profile: ProjectProfile, maturity: MaturityPrediction) -> BlockerResult:
        blockers: list[Blocker] = []
        diagnosed = stage(maturity.diagnosed_stage)

        if (profile.paying_customers or 0) == 0 and len(profile.market_validation_evidence) < 2:
            blockers.append(
                Blocker(
                    type=BlockerType.MARKET_VALIDATION,
                    severity=Severity.HIGH,
                    confidence=0.91,
                    priority=1,
                    evidence=["No paying customers", "Weak documented market validation"],
                    related_stage=MaturityStage.MARKET_VALIDATION,
                )
            )

        legal_stage_required = diagnosed in {
            MaturityStage.STRUCTURATION,
            MaturityStage.FUNDRAISING,
            MaturityStage.LAUNCH_PLANNING,
            MaturityStage.GROWTH,
        } or profile.primary_goal == "public_procurement"
        if legal_stage_required and (
            profile.legal_form is None or profile.formalization_status not in {"formalized", "registered"}
        ):
            blockers.append(
                Blocker(
                    type=BlockerType.LEGAL,
                    severity=Severity.MEDIUM,
                    confidence=0.72,
                    priority=2,
                    evidence=["Legal form or formalization status is incomplete"],
                    is_missing_information=profile.legal_form is None,
                    related_stage=MaturityStage.STRUCTURATION,
                )
            )

        if profile.primary_goal == "funding" and not profile.has_revenue and (profile.paying_customers or 0) == 0:
            blockers.append(
                Blocker(
                    type=BlockerType.FINANCIAL,
                    severity=Severity.HIGH,
                    confidence=0.84,
                    priority=3,
                    evidence=["Funding requested before revenue or customer proof"],
                    related_stage=MaturityStage.FUNDRAISING,
                )
            )

        if diagnosed == MaturityStage.GROWTH and (profile.process_automation_level or 0) < 0.45:
            blockers.append(
                Blocker(
                    type=BlockerType.SCALABILITY,
                    severity=Severity.HIGH,
                    confidence=0.86,
                    priority=2,
                    evidence=["Growth signal exists but delivery process remains manual"],
                    related_stage=MaturityStage.GROWTH,
                )
            )

        tender_probe = TenderReadinessProbe()
        tender_result = tender_probe.evaluate(profile)
        if tender_probe.should_activate(profile) and tender_result.status == TenderReadinessStatus.NOT_READY:
            blockers.append(
                Blocker(
                    type=BlockerType.TENDER_READINESS,
                    severity=Severity.HIGH,
                    confidence=0.88,
                    priority=1,
                    evidence=tender_result.evidence or ["Tender readiness criteria are insufficient"],
                    is_missing_information=bool(tender_result.missing_fields),
                    related_stage=MaturityStage.STRUCTURATION,
                )
            )

        blockers = sorted(
            blockers,
            key=lambda item: (SEVERITY_ORDER[Severity(item.severity)], item.priority, item.type),
        )
        for index, blocker in enumerate(blockers, start=1):
            blocker.priority = index
        return BlockerResult(blockers=blockers, model_version=self.version)
