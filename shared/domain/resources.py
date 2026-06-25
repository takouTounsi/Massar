from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.contracts.enums import CountryCode, MaturityStage
from shared.contracts.schemas import (
    BlockerResult,
    CompositeScores,
    MaturityPrediction,
    ProjectProfile,
    ResourceMatch,
)
from shared.domain.utils import stage

RESOURCE_FILE = Path(__file__).resolve().parents[2] / "data" / "knowledge_base" / "resources.json"


def _load_resources() -> list[dict[str, Any]]:
    if not RESOURCE_FILE.exists():
        return []
    return json.loads(RESOURCE_FILE.read_text(encoding="utf-8"))


def match_resources(
    profile: ProjectProfile,
    maturity: MaturityPrediction,
    scores: CompositeScores,
    blockers: BlockerResult,
    limit: int = 3,
) -> list[ResourceMatch]:
    resources = _load_resources()
    diagnosed = stage(maturity.diagnosed_stage)
    blocker_types = {str(blocker.type) for blocker in blockers.blockers}
    weak_scores = {score.name for score in scores.scores if score.value < 55}
    ranked: list[tuple[float, dict[str, Any], list[str]]] = []

    for resource in resources:
        relevance = 0.0
        reasons: list[str] = []

        if resource.get("country") == profile.country:
            relevance += 0.32
            reasons.append("Country match")
        if diagnosed.value in resource.get("eligible_stages", []):
            relevance += 0.24
            reasons.append(f"{diagnosed.value} stage")
        if profile.business_type in resource.get("target_profiles", []):
            relevance += 0.12
            reasons.append("Business type match")
        if profile.primary_goal and profile.primary_goal in resource.get("needs", []):
            relevance += 0.14
            reasons.append(f"{profile.primary_goal} need")
        if blocker_types.intersection(set(resource.get("blockers", []))):
            relevance += 0.12
            reasons.append("Blocker match")
        if weak_scores.intersection(set(resource.get("score_focus", []))):
            relevance += 0.06
            reasons.append("Weak score focus")

        if relevance > 0:
            ranked.append((min(relevance, 1.0), resource, reasons))

    ranked.sort(key=lambda item: item[0], reverse=True)
    matches: list[ResourceMatch] = []
    for relevance, resource, reasons in ranked[:limit]:
        matches.append(
            ResourceMatch(
                resource_id=resource["id"],
                name=resource["name"],
                institution=resource["institution"],
                country=CountryCode(resource["country"]),
                type=resource["resource_type"],
                relevance_score=round(relevance, 2),
                source_url=resource["source_url"],
                source_chunk_ids=resource.get("source_chunk_ids", [f"{resource['id']}-chunk-001"]),
                matched_reasons=reasons,
                eligible_stages=[MaturityStage(item) for item in resource.get("eligible_stages", [])],
                eligibility_conditions=resource.get("eligibility_conditions", []),
                synthetic=bool(resource.get("synthetic", True)),
            )
        )
    return matches
