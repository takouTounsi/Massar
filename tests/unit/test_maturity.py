from shared.contracts.enums import GapLevel, MaturityStage
from shared.domain.maturity import RuleBasedMaturityPredictor
from shared.testing import case_market_validation_gap


def test_fundraising_declared_without_customers_is_market_validation_high_gap() -> None:
    profile = case_market_validation_gap()
    prediction = RuleBasedMaturityPredictor().predict(profile)

    assert prediction.diagnosed_stage == MaturityStage.MARKET_VALIDATION
    assert prediction.declared_stage == MaturityStage.FUNDRAISING
    assert prediction.gap_level == GapLevel.HIGH
    assert "MATURITY-VAL-003" in prediction.triggered_rules
