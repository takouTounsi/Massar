from pydantic import BaseModel

from shared.application.fastapi import create_service_app
from shared.contracts.schemas import BlockerResult, CompositeScores, MaturityPrediction, ProjectProfile, ResourceMatch
from shared.domain.resources import match_resources

app = create_service_app("Resource Service", "resource_service")


class ResourceEnvelope(BaseModel):
    profile: ProjectProfile
    maturity: MaturityPrediction
    scores: CompositeScores
    blockers: BlockerResult
    limit: int = 3


@app.post("/resources/match", response_model=list[ResourceMatch])
async def resources(payload: ResourceEnvelope) -> list[ResourceMatch]:
    return match_resources(payload.profile, payload.maturity, payload.scores, payload.blockers, payload.limit)
