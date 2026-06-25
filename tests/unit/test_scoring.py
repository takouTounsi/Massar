from shared.domain.scoring import WeightedRuleScoreCalculator
from shared.testing import case_scalability_gap


def test_growth_saas_with_manual_processes_has_low_scalability_score() -> None:
    profile = case_scalability_gap()
    scores = WeightedRuleScoreCalculator().calculate(profile).by_name()

    assert scores["scalability_score"].value < 55
    assert "manual_processes_limit_growth" in scores["scalability_score"].anomalies
