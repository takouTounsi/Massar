from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.roadmap_service.app.schemas import (
    GeneratedRoadmap,
    GeneratedRoadmapAction,
    MissingInformationAction,
    RoadmapGenerationInput,
    RoadmapSummary,
)

TEMPLATE_FILE = Path(__file__).resolve().parents[1] / "data" / "roadmap_templates.json"
SEVERITY_WEIGHT = {"CRITICAL": 100, "HIGH": 80, "MEDIUM": 55, "LOW": 25}
HORIZON_ORDER = {"IMMEDIATE": 0, "SHORT_TERM": 1, "MEDIUM_TERM": 2}


def load_templates() -> dict[str, Any]:
    return json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))


def generate_roadmap(payload: RoadmapGenerationInput) -> GeneratedRoadmap:
    template_data = load_templates()
    actions: list[GeneratedRoadmapAction] = []
    used_keys: set[str] = set()
    weak_scores = {score for score, value in payload.scores.items() if value < 55}
    resource_ids = {resource.resource_id for resource in payload.resources}
    resources_by_id = {resource.resource_id: resource for resource in payload.resources}

    for blocker in sorted(payload.blockers, key=lambda item: item.priority_rank):
        for template in template_data["templates"]:
            action_key = template["action_key"]
            if action_key in used_keys:
                continue
            triggered = blocker.type in template.get("triggered_by_blockers", [])
            recommended = blocker.recommended_action_key == action_key
            if not triggered and not recommended:
                continue
            if _is_future_stage_action(payload, template):
                continue
            linked_resources = _linked_resources(payload, action_key, resource_ids)
            actions.append(
                _build_action(
                    template=template,
                    priority_seed=SEVERITY_WEIGHT.get(blocker.severity, 30) + template.get("priority_weight", 0),
                    blockers=[blocker.type],
                    scores=list(set(template.get("triggered_by_weak_scores", [])) & weak_scores),
                    evidence=blocker.evidence,
                    resource_ids=linked_resources,
                    source_urls=[resources_by_id[item].source_url for item in linked_resources if item in resources_by_id],
                )
            )
            used_keys.add(action_key)

    for score in sorted(weak_scores):
        for template in template_data["templates"]:
            action_key = template["action_key"]
            if action_key in used_keys:
                continue
            if score not in template.get("triggered_by_weak_scores", []):
                continue
            if _is_future_stage_action(payload, template):
                continue
            linked_resources = _linked_resources(payload, action_key, resource_ids)
            actions.append(
                _build_action(
                    template=template,
                    priority_seed=template.get("priority_weight", 0),
                    blockers=[],
                    scores=[score],
                    evidence=[f"{score} is weak"],
                    resource_ids=linked_resources,
                    source_urls=[resources_by_id[item].source_url for item in linked_resources if item in resources_by_id],
                )
            )
            used_keys.add(action_key)

    missing_actions = [
        MissingInformationAction(
            field=field,
            reason=f"Required to make the next diagnosis more reliable: {field}",
        )
        for field in payload.missing_fields
    ]

    actions = sorted(
        actions,
        key=lambda item: (HORIZON_ORDER.get(item.horizon, 99), item.priority),
    )[:8]
    for index, action in enumerate(actions, start=1):
        action.priority = index

    return GeneratedRoadmap(
        project_id=payload.project_id,
        roadmap_version=template_data.get("version", "roadmap-rules-v0.1.0"),
        summary=RoadmapSummary(
            current_focus=_focus(payload),
            next_stage_target=_next_stage(payload.diagnosed_stage),
            confidence=round(min(0.95, max(0.35, payload.maturity_confidence - 0.02)), 2),
        ),
        actions=actions,
        missing_information_actions=missing_actions,
    )


def _build_action(
    *,
    template: dict[str, Any],
    priority_seed: int,
    blockers: list[str],
    scores: list[str],
    evidence: list[str],
    resource_ids: list[str],
    source_urls: list[str],
) -> GeneratedRoadmapAction:
    action = template["action"]
    return GeneratedRoadmapAction(
        title=action["title"],
        description=action["description"],
        horizon=action["horizon"],
        priority=max(1, 200 - priority_seed),
        estimated_effort=action["estimated_effort"],
        addresses_blockers=blockers,
        improves_scores=scores,
        evidence=evidence or ["Triggered by diagnostic data"],
        resource_ids=resource_ids,
        source_urls=source_urls,
        reason=_reason(blockers, scores),
    )


def _linked_resources(payload: RoadmapGenerationInput, action_key: str, resource_ids: set[str]) -> list[str]:
    if action_key == "customer_validation":
        candidates = ["tn_resource_001"]
    elif action_key == "tender_readiness":
        candidates = ["tn_resource_002"]
    elif action_key == "export_readiness":
        candidates = ["tn_resource_003", "tn_resource_004"]
    else:
        candidates = [resource.resource_id for resource in payload.resources]
    return [item for item in candidates if item in resource_ids][:2]


def _is_future_stage_action(payload: RoadmapGenerationInput, template: dict[str, Any]) -> bool:
    if payload.diagnosed_stage == "MARKET_VALIDATION" and template["action_key"] in {"fundraising", "export_readiness"}:
        return True
    applicable = set(template.get("applicable_stages", []))
    return bool(applicable) and payload.diagnosed_stage not in applicable


def _reason(blockers: list[str], scores: list[str]) -> str:
    if blockers and scores:
        return f"Addresses {', '.join(blockers)} and improves {', '.join(scores)}"
    if blockers:
        return f"Addresses {', '.join(blockers)}"
    return f"Improves {', '.join(scores)}"


def _focus(payload: RoadmapGenerationInput) -> str:
    if payload.diagnosed_stage == "MARKET_VALIDATION":
        return "Validate demand before pursuing fundraising"
    if payload.primary_goal == "public_procurement":
        return "Become tender-ready before bidding"
    if payload.primary_goal == "export":
        return "Prepare export readiness and documentation"
    return "Resolve the highest-priority blockers"


def _next_stage(stage: str) -> str:
    order = ["IDEATION", "MARKET_VALIDATION", "STRUCTURATION", "FUNDRAISING", "LAUNCH_PLANNING", "GROWTH"]
    try:
        return order[min(order.index(stage) + 1, len(order) - 1)]
    except ValueError:
        return "STRUCTURATION"
