from shared.contracts.enums import BusinessType, CountryCode, MaturityStage
from shared.contracts.schemas import ProjectProfile
from shared.domain.blockers import RuleBasedBlockerDetector
from shared.domain.confidence import assess_confidence
from shared.domain.maturity import RuleBasedMaturityPredictor
from shared.domain.scoring import WeightedRuleScoreCalculator


def test_incomplete_profile_exposes_missing_fields_without_crashing() -> None:
    profile = ProjectProfile(
        country=CountryCode.TN,
        business_type=BusinessType.STARTUP,
        declared_stage=MaturityStage.IDEATION,
    )
    maturity = RuleBasedMaturityPredictor().predict(profile)
    scores = WeightedRuleScoreCalculator().calculate(profile)
    blockers = RuleBasedBlockerDetector().detect(profile, maturity)
    confidence = assess_confidence(profile, maturity, scores, blockers)

    assert confidence.overall_confidence < 0.8
    assert "monthly_revenue" in confidence.missing_fields
    assert confidence.manual_review_required is False
