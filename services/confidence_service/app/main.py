from pydantic import BaseModel

from shared.application.fastapi import create_service_app
from shared.contracts.schemas import BlockerResult, CompositeScores, ConfidenceReport, MaturityPrediction, ProjectProfile
from shared.domain.confidence import assess_confidence

app = create_service_app("Confidence Service", "confidence_service")


class ConfidenceEnvelope(BaseModel):
    profile: ProjectProfile
    maturity: MaturityPrediction
    scores: CompositeScores
    blockers: BlockerResult


@app.post("/confidence/assess", response_model=ConfidenceReport)
async def confidence(payload: ConfidenceEnvelope) -> ConfidenceReport:
    return assess_confidence(payload.profile, payload.maturity, payload.scores, payload.blockers)
