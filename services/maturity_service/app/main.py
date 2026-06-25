from shared.application.fastapi import create_service_app
from shared.contracts.schemas import MaturityPrediction, ProjectProfile
from shared.domain.maturity import RuleBasedMaturityPredictor, SklearnMaturityPredictor

app = create_service_app("Maturity Service", "maturity_service")
predictor = RuleBasedMaturityPredictor()


@app.post("/maturity/predict", response_model=MaturityPrediction)
async def predict_maturity(profile: ProjectProfile) -> MaturityPrediction:
    return predictor.predict(profile)


@app.post("/maturity/predict/sklearn", response_model=MaturityPrediction)
async def predict_maturity_sklearn(profile: ProjectProfile) -> MaturityPrediction:
    return SklearnMaturityPredictor().predict(profile)
