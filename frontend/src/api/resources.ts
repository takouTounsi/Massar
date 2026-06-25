import { request } from "./client";
import type { Resource } from "./types";

export function getResources(projectId: string) {
  return request<Resource[]>(`/api/v1/projects/${projectId}/resources`);
}
