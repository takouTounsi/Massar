from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from shared.application.fastapi import create_service_app
from shared.contracts.schemas import ProgressEvent

app = create_service_app("Progress Service", "progress_service")
events: dict[UUID, list[ProgressEvent]] = {}


class CompletePayload(BaseModel):
    project_id: UUID


@app.post("/progress/actions/{action_id}/complete", response_model=ProgressEvent)
async def complete_action(action_id: str, payload: CompletePayload) -> ProgressEvent:
    event = ProgressEvent(project_id=payload.project_id, action_id=action_id)
    events.setdefault(payload.project_id, []).append(event)
    return event


@app.get("/progress/projects/{project_id}", response_model=list[ProgressEvent])
async def project_progress(project_id: UUID) -> list[ProgressEvent]:
    return events.get(project_id, [])


@app.get("/progress/projects/{project_id}/history", response_model=list[ProgressEvent])
async def project_history(project_id: UUID) -> list[ProgressEvent]:
    return events.get(project_id, [])
