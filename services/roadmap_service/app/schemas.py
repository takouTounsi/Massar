from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RoadmapResourceInput(BaseModel):
    resource_id: str
    name: str
    institution: str
    category: str
    eligibility_status: str
    source_url: str


class RoadmapBlockerInput(BaseModel):
    type: str
    severity: str
    priority_rank: int
    stage_blocking: bool = False
    recommended_action_key: str | None = None
    evidence: list[str] = Field(default_factory=list)


class RoadmapGenerationInput(BaseModel):
    project_id: UUID
    country: str
    business_type: str
    sector: str
    primary_goal: str
    declared_stage: str
    diagnosed_stage: str
    maturity_confidence: float
    scores: dict[str, float]
    score_details: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    blockers: list[RoadmapBlockerInput] = Field(default_factory=list)
    resources: list[RoadmapResourceInput] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class RoadmapSummary(BaseModel):
    current_focus: str
    next_stage_target: str
    confidence: float


class GeneratedRoadmapAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str
    horizon: str
    priority: int
    status: str = "TODO"
    estimated_effort: str
    addresses_blockers: list[str] = Field(default_factory=list)
    improves_scores: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    reason: str
    source_urls: list[str] = Field(default_factory=list)


class MissingInformationAction(BaseModel):
    field: str
    reason: str


class GeneratedRoadmap(BaseModel):
    roadmap_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    roadmap_version: str = "roadmap-rules-v0.1.0"
    summary: RoadmapSummary
    actions: list[GeneratedRoadmapAction]
    missing_information_actions: list[MissingInformationAction] = Field(default_factory=list)


class RoadmapStatusPatch(BaseModel):
    status: str
