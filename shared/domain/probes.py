from __future__ import annotations

from shared.contracts.enums import QuestionType, TenderReadinessStatus
from shared.contracts.schemas import ProjectProfile, Question, TenderProbeResult


class TenderReadinessProbe:
    code = "tender_readiness"

    def should_activate(self, profile: ProjectProfile) -> bool:
        return profile.primary_goal == "public_procurement" or profile.wants_public_tenders is True

    def questions(self, profile: ProjectProfile) -> list[Question]:
        if not self.should_activate(profile):
            return []
        return [
            Question(
                id="tender_001",
                code="administrative_documents_ready",
                text={
                    "fr": "Vos documents administratifs sont-ils prets pour un appel d'offres ?",
                    "ar": "هل الوثائق الادارية جاهزة للمناقصات؟",
                },
                type=QuestionType.BOOLEAN,
                tags=["tender_readiness", "administrative"],
            ),
            Question(
                id="tender_002",
                code="financial_capacity_score",
                text={
                    "fr": "Evaluez votre capacite financiere pour executer un marche public.",
                    "ar": "قيّم القدرة المالية لتنفيذ صفقة عمومية.",
                },
                type=QuestionType.INTEGER,
                validation={"min": 0, "max": 100},
                tags=["tender_readiness", "finance"],
            ),
            Question(
                id="tender_003",
                code="tender_references_count",
                text={
                    "fr": "Combien de references similaires pouvez-vous fournir ?",
                    "ar": "كم عدد المراجع المشابهة التي يمكن تقديمها؟",
                },
                type=QuestionType.INTEGER,
                validation={"min": 0},
                tags=["tender_readiness", "references"],
            ),
        ]

    def evaluate(self, profile: ProjectProfile) -> TenderProbeResult:
        if not self.should_activate(profile):
            return TenderProbeResult(status=TenderReadinessStatus.NOT_READY, score=0)

        missing = []
        score = 0
        evidence: list[str] = []

        if profile.administrative_documents_ready is None:
            missing.append("administrative_documents_ready")
        elif profile.administrative_documents_ready:
            score += 30
            evidence.append("Administrative documents ready")
        else:
            evidence.append("Administrative documents incomplete")

        if profile.financial_capacity_score is None:
            missing.append("financial_capacity_score")
        else:
            score += min(profile.financial_capacity_score, 100) // 3
            if profile.financial_capacity_score < 45:
                evidence.append("Weak financial capacity")

        refs = profile.tender_references_count
        if refs is None:
            missing.append("tender_references_count")
        else:
            score += min(refs * 12, 30)
            if refs == 0:
                evidence.append("No similar tender references")

        if score >= 78:
            status = TenderReadinessStatus.READY
        elif score >= 58:
            status = TenderReadinessStatus.READY_WITH_PARTNER
        elif score >= 42:
            status = TenderReadinessStatus.READY_FOR_SMALL_TENDERS
        else:
            status = TenderReadinessStatus.NOT_READY

        return TenderProbeResult(
            status=status,
            score=int(score),
            evidence=evidence,
            missing_fields=missing,
        )
