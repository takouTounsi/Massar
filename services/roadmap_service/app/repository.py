from __future__ import annotations

from uuid import UUID

from services.roadmap_service.app.schemas import GeneratedRoadmap


class InMemoryRoadmapRepository:
    def __init__(self) -> None:
        self._by_project: dict[str, GeneratedRoadmap] = {}

    def save(self, roadmap: GeneratedRoadmap) -> GeneratedRoadmap:
        self._by_project[str(roadmap.project_id)] = roadmap
        return roadmap

    def get(self, project_id: UUID) -> GeneratedRoadmap | None:
        return self._by_project.get(str(project_id))

    def patch_action(self, project_id: UUID, action_id: str, status: str) -> GeneratedRoadmap | None:
        roadmap = self.get(project_id)
        if roadmap is None:
            return None
        for action in roadmap.actions:
            if action.id == action_id:
                action.status = status
                return roadmap
        return None


roadmap_repository = InMemoryRoadmapRepository()
