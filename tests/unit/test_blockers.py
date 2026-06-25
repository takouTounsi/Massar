from shared.contracts.enums import BlockerType
from shared.domain.blockers import RuleBasedBlockerDetector
from shared.domain.maturity import RuleBasedMaturityPredictor
from shared.testing import case_market_validation_gap


def test_blockers_prioritize_market_validation_and_financial_for_demo_case() -> None:
    profile = case_market_validation_gap()
    maturity = RuleBasedMaturityPredictor().predict(profile)
    result = RuleBasedBlockerDetector().detect(profile, maturity)
    blocker_types = [blocker.type for blocker in result.blockers]

    assert blocker_types[:2] == [BlockerType.MARKET_VALIDATION, BlockerType.FINANCIAL]
    assert len(result.blockers) == 2
