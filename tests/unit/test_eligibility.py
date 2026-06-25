from shared.domain.blockers import RuleBasedBlockerDetector
from shared.domain.eligibility import evaluate_eligibility
from shared.domain.maturity import RuleBasedMaturityPredictor
from shared.domain.resources import match_resources
from shared.domain.scoring import WeightedRuleScoreCalculator
from shared.testing import case_market_validation_gap


def test_eligibility_keeps_missing_conditions_visible() -> None:
    profile = case_market_validation_gap()
    maturity = RuleBasedMaturityPredictor().predict(profile)
    scores = WeightedRuleScoreCalculator().calculate(profile)
    blockers = RuleBasedBlockerDetector().detect(profile, maturity)
    resources = match_resources(profile, maturity, scores, blockers)
    results = evaluate_eligibility(profile, resources)

    assert len(resources) == 3
    assert any(result.status in {"POSSIBLY_ELIGIBLE", "ELIGIBLE"} for result in results)
    assert any(result.missing_conditions for result in results)
