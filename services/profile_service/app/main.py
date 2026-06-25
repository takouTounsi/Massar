from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel

from shared.application import InMemoryOrientationPipeline
from shared.application.fastapi import create_service_app
from shared.contracts.schemas import (
    AnalysisResult,
    DashboardResponse,
    ProjectCreateRequest,
    ProjectProfile,
)

app = create_service_app("Profile Service", "profile_service")
pipeline = InMemoryOrientationPipeline()


class PatchPayload(BaseModel):
    patch: dict[str, Any]


class ProgressPayload(BaseModel):
    action_id: str


@app.post("/profiles/projects", response_model=ProjectProfile)
async def create_project(payload: ProjectCreateRequest) -> ProjectProfile:
    return pipeline.create_project(payload)


@app.get("/profiles/projects/{project_id}", response_model=ProjectProfile)
async def get_project(project_id: UUID) -> ProjectProfile:
    try:
        return pipeline.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@app.patch("/profiles/projects/{project_id}", response_model=ProjectProfile)
async def patch_project(project_id: UUID, payload: PatchPayload) -> ProjectProfile:
    try:
        return pipeline.update_project(project_id, dict(payload.patch))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@app.post("/profiles/projects/{project_id}/analysis", response_model=AnalysisResult)
async def save_analysis(project_id: UUID, analysis: AnalysisResult) -> AnalysisResult:
    return pipeline.save_analysis(project_id, analysis)


@app.get("/profiles/projects/{project_id}/dashboard", response_model=DashboardResponse)
async def dashboard(project_id: UUID) -> DashboardResponse:
    try:
        return pipeline.dashboard(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@app.get("/profiles/projects/{project_id}/roadmap")
async def roadmap(project_id: UUID):
    try:
        return pipeline.roadmap(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Roadmap not found") from exc


@app.post("/profiles/projects/{project_id}/progress", response_model=DashboardResponse)
async def save_progress(project_id: UUID, payload: ProgressPayload) -> DashboardResponse:
    return pipeline.complete_action(project_id, payload.action_id)
