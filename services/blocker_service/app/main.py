from pydantic import BaseModel

from shared.application.fastapi import create_service_app
from shared.contracts.schemas import BlockerResult, MaturityPrediction, ProjectProfile
from shared.domain.blockers import RuleBasedBlockerDetector

app = create_service_app("Blocker Service", "blocker_service")
detector = RuleBasedBlockerDetector()


class BlockerEnvelope(BaseModel):
    profile: ProjectProfile
    maturity: MaturityPrediction


@app.post("/blockers/detect", response_model=BlockerResult)
async def detect_blockers(payload: BlockerEnvelope) -> BlockerResult:
    return detector.detect(payload.profile, payload.maturity)
