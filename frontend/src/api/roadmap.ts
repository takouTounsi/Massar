import { request } from "./client";
import type { GeneratedRoadmap } from "./types";

export function getRoadmap(projectId: string) {
  return request<GeneratedRoadmap>(`/api/v1/projects/${projectId}/roadmap`);
}

export function generateRoadmap(projectId: string) {
  return request<GeneratedRoadmap>(`/api/v1/projects/${projectId}/roadmap/generate`, {
    method: "POST"
  });
}

export function updateRoadmapAction(projectId: string, actionId: string, status: string) {
  return request<GeneratedRoadmap>(`/api/v1/projects/${projectId}/roadmap/actions/${actionId}`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
}

export function regenerateRoadmap(projectId: string) {
  return request<GeneratedRoadmap>(`/api/v1/projects/${projectId}/roadmap/regenerate`, {
    method: "POST"
  });
}
