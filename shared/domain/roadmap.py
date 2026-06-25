from __future__ import annotations

from uuid import uuid4

from shared.contracts.enums import BlockerType, RoadmapHorizon
from shared.contracts.schemas import (
    BlockerResult,
    CompositeScores,
    EligibilityResult,
    ProjectProfile,
    ResourceMatch,
    Roadmap,
    RoadmapAction,
)


def build_roadmap(
    profile: ProjectProfile,
    blockers: BlockerResult,
    scores: CompositeScores,
    resources: list[ResourceMatch],
    eligibility: list[EligibilityResult],
) -> Roadmap:
    resource_ids = {resource.resource_id for resource in resources}
    usable_resources = {
        item.resource_id
        for item in eligibility
        if item.resource_id in resource_ids and item.status in {"ELIGIBLE", "POSSIBLY_ELIGIBLE"}
    }
    actions: list[RoadmapAction] = []

    for blocker in blockers.blockers[:4]:
        title = _title_for_blocker(str(blocker.type))
        score_name = _score_for_blocker(str(blocker.type))
        linked_resources = list(usable_resources)[:1] if usable_resources else []
        actions.append(
            RoadmapAction(
                id=f"action-{len(actions) + 1:03d}",
                title=title,
                horizon=RoadmapHorizon.IMMEDIATE if blocker.priority <= 2 else RoadmapHorizon.SHORT_TERM,
                priority=len(actions) + 1,
                rationale="; ".join(blocker.evidence),
                addresses_blocker_ids=[blocker.id],
                addresses_score=score_name,
                resource_ids=linked_resources,
                depends_on=[] if not actions else [actions[-1].id] if blocker.priority > 2 else [],
            )
        )

    weak_scores = [score for score in scores.scores if score.value < 55]
    for score in weak_scores[:2]:
        actions.append(
            RoadmapAction(
                id=f"action-{len(actions) + 1:03d}",
                title=score.highest_leverage_action,
                horizon=RoadmapHorizon.SHORT_TERM,
                priority=len(actions) + 1,
                rationale=f"{score.name} is {score.value}/100",
                addresses_score=score.name,
                resource_ids=[],
                depends_on=[actions[0].id] if actions else [],
            )
        )

    if not actions:
        actions.append(
            RoadmapAction(
                id="action-001",
                title="Prepare the next diagnostic review",
                horizon=RoadmapHorizon.MEDIUM_TERM,
                priority=1,
                rationale="No critical blocker was detected",
            )
        )

    _validate_resource_grounding(actions, resource_ids)
    return Roadmap(project_id=profile.project_id, roadmap_id=uuid4(), actions=actions)


def _title_for_blocker(blocker_type: str) -> str:
    titles = {
        BlockerType.MARKET_VALIDATION.value: "Run structured market validation interviews",
        BlockerType.LEGAL.value: "Clarify legal form and formalization status",
        BlockerType.FINANCIAL.value: "Build funding readiness evidence",
        BlockerType.SCALABILITY.value: "Automate the highest-volume manual process",
        BlockerType.TENDER_READINESS.value: "Complete tender readiness prerequisites",
    }
    return titles.get(blocker_type, "Resolve the highest-priority blocker")


def _score_for_blocker(blocker_type: str) -> str | None:
    mapping = {
        BlockerType.MARKET_VALIDATION.value: "market_score",
        BlockerType.LEGAL.value: "commercial_offer_score",
        BlockerType.FINANCIAL.value: "market_score",
        BlockerType.SCALABILITY.value: "scalability_score",
        BlockerType.TENDER_READINESS.value: "commercial_offer_score",
    }
    return mapping.get(blocker_type)


def _validate_resource_grounding(actions: list[RoadmapAction], resource_ids: set[str]) -> None:
    for action in actions:
        unknown = set(action.resource_ids) - resource_ids
        if unknown:
            raise ValueError(f"Roadmap action {action.id} references unknown resources: {unknown}")
