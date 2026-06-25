from shared.domain.blockers import RuleBasedBlockerDetector
from shared.domain.eligibility import evaluate_eligibility
from shared.domain.maturity import RuleBasedMaturityPredictor
from shared.domain.resources import match_resources
from shared.domain.roadmap import build_roadmap
from shared.domain.scoring import WeightedRuleScoreCalculator
from shared.testing import case_market_validation_gap


def test_roadmap_references_only_existing_resources() -> None:
    profile = case_market_validation_gap()
    maturity = RuleBasedMaturityPredictor().predict(profile)
    scores = WeightedRuleScoreCalculator().calculate(profile)
    blockers = RuleBasedBlockerDetector().detect(profile, maturity)
    resources = match_resources(profile, maturity, scores, blockers)
    eligibility = evaluate_eligibility(profile, resources)
    roadmap = build_roadmap(profile, blockers, scores, resources, eligibility)
    resource_ids = {resource.resource_id for resource in resources}

    assert roadmap.actions
    assert all(set(action.resource_ids).issubset(resource_ids) for action in roadmap.actions)
