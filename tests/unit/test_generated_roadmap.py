from uuid import UUID

from services.roadmap_service.app.generator import generate_roadmap
from services.roadmap_service.app.repository import InMemoryRoadmapRepository
from services.roadmap_service.app.schemas import RoadmapGenerationInput
from shared.demo_data import build_demo_dashboard


DEMO_PROJECT_ID = UUID("11111111-1111-4111-8111-111111111111")


def _demo_payload() -> RoadmapGenerationInput:
    dashboard = build_demo_dashboard(str(DEMO_PROJECT_ID))
    assert dashboard is not None
    project = dashboard["project"]
    analysis = dashboard["analysis"]
    return RoadmapGenerationInput(
        project_id=DEMO_PROJECT_ID,
        country=project["country"],
        business_type=project["business_type"],
        sector=project["sector"],
        primary_goal=project["primary_goal"],
        declared_stage=analysis["declared_stage"],
        diagnosed_stage=analysis["diagnosed_stage"],
        maturity_confidence=analysis["maturity_confidence"],
        scores=analysis["scores"],
        score_details=analysis["score_details"],
        blockers=analysis["blockers"],
        resources=analysis["resources"],
        missing_fields=analysis["missing_fields"],
    )


def test_generated_roadmap_is_prioritized_and_grounded_in_resources() -> None:
    payload = _demo_payload()
    roadmap = generate_roadmap(payload)
    resource_ids = {resource.resource_id for resource in payload.resources}

    assert 1 <= len(roadmap.actions) <= 8
    assert roadmap.actions[0].horizon == "IMMEDIATE"
    assert all(set(action.resource_ids).issubset(resource_ids) for action in roadmap.actions)
    assert all("export" not in action.title.lower() for action in roadmap.actions)
    assert roadmap.summary.next_stage_target == "STRUCTURATION"


def test_roadmap_repository_updates_action_status() -> None:
    repository = InMemoryRoadmapRepository()
    roadmap = repository.save(generate_roadmap(_demo_payload()))
    action_id = roadmap.actions[0].id

    updated = repository.patch_action(DEMO_PROJECT_ID, action_id, "COMPLETED")

    assert updated is not None
    assert updated.actions[0].status == "COMPLETED"
