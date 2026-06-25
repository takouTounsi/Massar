from __future__ import annotations

from shared.contracts.schemas import (
    BlockerResult,
    CompositeScores,
    ConfidenceReport,
    MaturityPrediction,
    ProjectProfile,
)


def assess_confidence(
    profile: ProjectProfile,
    maturity: MaturityPrediction,
    scores: CompositeScores,
    blockers: BlockerResult,
) -> ConfidenceReport:
    missing_fields = [
        field
        for field in [
            "monthly_revenue",
            "customer_retention",
            "market_size_known",
            "competition_understanding",
            "revenue_model_clarity",
            "process_automation_level",
        ]
        if getattr(profile, field, None) is None and field != "customer_retention"
    ]
    if "customer_retention" not in profile.extra_answers:
        missing_fields.append("customer_retention")

    ambiguous_fields = []
    if profile.market_size_known is None:
        ambiguous_fields.append("market_size")
    if profile.has_revenue is False and (profile.monthly_revenue or 0) > 0:
        ambiguous_fields.append("has_revenue")

    score_confidence = sum(score.confidence for score in scores.scores) / len(scores.scores)
    blocker_confidence = (
        sum(blocker.confidence for blocker in blockers.blockers) / len(blockers.blockers)
        if blockers.blockers
        else 0.75
    )
    base = (maturity.confidence + score_confidence + blocker_confidence) / 3
    penalty = min(len(missing_fields) * 0.025 + len(ambiguous_fields) * 0.05, 0.28)
    overall = max(0.2, min(0.95, base - penalty))
    return ConfidenceReport(
        overall_confidence=round(overall, 2),
        missing_fields=missing_fields,
        ambiguous_fields=ambiguous_fields,
        manual_review_required=overall < 0.25 or len(ambiguous_fields) >= 2,
    )
