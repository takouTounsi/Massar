import { request, uploadFile } from "./client";
import type { DemoDashboard, EvidenceAttachment, IntakeSession, ProjectProfile } from "./types";

export function listProjects() {
  return request<ProjectProfile[]>("/api/v1/projects");
}

export function createProject(payload: Record<string, unknown>) {
  return request<ProjectProfile>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function startIntake(projectId: string) {
  return request<IntakeSession>(`/api/v1/projects/${projectId}/intake/start`, { method: "POST" });
}

export function answerIntake(projectId: string, payload: Record<string, unknown>) {
  return request<{ session: IntakeSession }>(`/api/v1/projects/${projectId}/intake/answer`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function runAnalysis(projectId: string) {
  return request<unknown>(`/api/v1/projects/${projectId}/analysis/run`, { method: "POST" });
}

export function getProjectDashboard(projectId: string) {
  return request<DemoDashboard>(`/api/v1/projects/${projectId}/dashboard`);
}

export function uploadIntakeEvidence(
  projectId: string,
  file: File,
  meta: { sessionId?: string; questionCode?: string },
  onProgress?: (percent: number) => void
) {
  const form = new FormData();
  form.append("file", file);
  if (meta.sessionId) form.append("session_id", meta.sessionId);
  if (meta.questionCode) form.append("question_code", meta.questionCode);
  return uploadFile<EvidenceAttachment>(`/api/v1/projects/${projectId}/intake/evidence`, form, onProgress);
}

export function listIntakeEvidence(projectId: string, sessionId?: string) {
  const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return request<EvidenceAttachment[]>(`/api/v1/projects/${projectId}/intake/evidence${query}`);
}
