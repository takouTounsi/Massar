from shared.application.fastapi import create_service_app
from shared.contracts.schemas import CompositeScores, ProjectProfile
from shared.domain.scoring import ModelBasedScoreCalculator, WeightedRuleScoreCalculator

app = create_service_app("Scoring Service", "scoring_service")
calculator = WeightedRuleScoreCalculator()


@app.post("/scores/calculate", response_model=CompositeScores)
async def calculate_scores(profile: ProjectProfile) -> CompositeScores:
    return calculator.calculate(profile)


@app.post("/scores/calculate/model", response_model=CompositeScores)
async def calculate_model_scores(profile: ProjectProfile) -> CompositeScores:
    return ModelBasedScoreCalculator().calculate(profile)
