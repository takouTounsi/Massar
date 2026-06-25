from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def _load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


@lru_cache
def demo_profiles() -> list[dict[str, Any]]:
    return list(_load("demo_profiles.json")["projects"])


@lru_cache
def demo_resources() -> list[dict[str, Any]]:
    return list(_load("demo_resources.json")["resources"])


@lru_cache
def demo_analyses() -> dict[str, dict[str, Any]]:
    return dict(_load("demo_analysis.json")["analyses"])


def get_demo_project(project_id: str) -> dict[str, Any] | None:
    return next((project for project in demo_profiles() if project["project_id"] == project_id), None)


def get_project_resources(project_id: str) -> list[dict[str, Any]]:
    analysis = demo_analyses().get(project_id)
    if not analysis:
        return []
    allowed_ids = set(analysis.get("resource_ids", []))
    return [resource for resource in demo_resources() if resource["resource_id"] in allowed_ids]


def build_demo_dashboard(project_id: str) -> dict[str, Any] | None:
    project = get_demo_project(project_id)
    analysis = demo_analyses().get(project_id)
    if not project or not analysis:
        return None
    return {
        "project": project,
        "analysis": {
            **analysis,
            "resources": get_project_resources(project_id),
        },
    }
