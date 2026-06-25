from pydantic import BaseModel

from shared.application.fastapi import create_service_app
from shared.contracts.schemas import EligibilityResult, ProjectProfile, ResourceMatch
from shared.domain.eligibility import evaluate_eligibility

app = create_service_app("Eligibility Service", "eligibility_service")


class EligibilityEnvelope(BaseModel):
    profile: ProjectProfile
    resources: list[ResourceMatch]


@app.post("/eligibility/check", response_model=list[EligibilityResult])
async def eligibility(payload: EligibilityEnvelope) -> list[EligibilityResult]:
    return evaluate_eligibility(payload.profile, payload.resources)
