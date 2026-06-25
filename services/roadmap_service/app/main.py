from pydantic import BaseModel
from fastapi import HTTPException
from uuid import UUID

from shared.application.fastapi import create_service_app
from shared.contracts.schemas import (
    BlockerResult,
    CompositeScores,
    EligibilityResult,
    ProjectProfile,
    ResourceMatch,
    Roadmap,
)
from shared.domain.roadmap import build_roadmap
from services.roadmap_service.app.generator import generate_roadmap
from services.roadmap_service.app.repository import roadmap_repository
from services.roadmap_service.app.schemas import (
    GeneratedRoadmap,
    RoadmapGenerationInput,
    RoadmapStatusPatch,
)

app = create_service_app("Roadmap Service", "roadmap_service")


class RoadmapEnvelope(BaseModel):
    profile: ProjectProfile
    blockers: BlockerResult
    scores: CompositeScores
    resources: list[ResourceMatch]
    eligibility: list[EligibilityResult]


@app.post("/roadmaps/build", response_model=Roadmap)
async def roadmap(payload: RoadmapEnvelope) -> Roadmap:
    return build_roadmap(
        payload.profile,
        payload.blockers,
        payload.scores,
        payload.resources,
        payload.eligibility,
    )


@app.post("/api/v1/projects/{project_id}/roadmap/generate", response_model=GeneratedRoadmap)
async def generate_project_roadmap(project_id: UUID, payload: RoadmapGenerationInput) -> GeneratedRoadmap:
    if payload.project_id != project_id:
        raise HTTPException(status_code=422, detail="Project id mismatch")
    roadmap = generate_roadmap(payload)
    return roadmap_repository.save(roadmap)


@app.get("/api/v1/projects/{project_id}/roadmap", response_model=GeneratedRoadmap)
async def get_project_roadmap(project_id: UUID) -> GeneratedRoadmap:
    roadmap = roadmap_repository.get(project_id)
    if roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap


@app.patch("/api/v1/projects/{project_id}/roadmap/actions/{action_id}", response_model=GeneratedRoadmap)
async def patch_project_roadmap_action(
    project_id: UUID,
    action_id: str,
    payload: RoadmapStatusPatch,
) -> GeneratedRoadmap:
    if payload.status not in {"TODO", "IN_PROGRESS", "COMPLETED", "DONE"}:
        raise HTTPException(status_code=422, detail="Unsupported action status")
    normalized = "COMPLETED" if payload.status == "DONE" else payload.status
    roadmap = roadmap_repository.patch_action(project_id, action_id, normalized)
    if roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap or action not found")
    return roadmap


@app.post("/api/v1/projects/{project_id}/roadmap/regenerate", response_model=GeneratedRoadmap)
async def regenerate_project_roadmap(project_id: UUID, payload: RoadmapGenerationInput) -> GeneratedRoadmap:
    return await generate_project_roadmap(project_id, payload)
