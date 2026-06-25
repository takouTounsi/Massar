// Client for the Adaptive Intake Engine (evidence-ledger driven, free-text AR/FR).
// Talks to the public gateway, which proxies to the intake service.

export type AdaptiveQuestion = {
  id: string;
  code: string;
  text: Record<string, string>; // { fr, ar }
  type: string;
  options: string[];
  tags: string[];
};

export type SessionStart = {
  session_id: string;
  first_question: AdaptiveQuestion | null;
};

export type Contradiction = {
  rule_id: string;
  field: string;
  reason: string;
};

export type AnswerResult = {
  next_question: AdaptiveQuestion | null;
  diagnostic_ready: boolean;
  fired_probes: string[];
  contradictions: Contradiction[];
};

export type SessionState = {
  phase: string;
  // Frontier-relative progress (no fixed answered/total denominator).
  frontier_stage: string;
  next_stage: string | null;
  gates_satisfied: number;
  gates_total: number;
  percent_to_next: number;
  declared_stage: string | null;
  completed: boolean;
};

export type SubScore = {
  name: string;
  value: number;
  weight: number;
  contribution: number;
};

export type Score = {
  name: string;
  value: number;
  confidence: number;
  sub_scores: SubScore[];
  missing_criteria: string[];
  anomalies: string[];
  highest_leverage_action: string;
};

export type LedgerEntry = {
  field: string;
  value: unknown;
  status: string;
};

export type Diagnosis = {
  session_id: string;
  completed: boolean;
  frontier_stage: string;
  declared_stage: string | null;
  diagnosis: {
    diagnosed_stage: string;
    declared_stage: string;
    gap_level: string;
    confidence: number;
    triggered_rules: string[];
  };
  scores: { scores: Score[]; version: string };
  ledger: Record<string, LedgerEntry>;
};

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5050";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function startSession(lang: string, projectId?: string) {
  return request<SessionStart>("/api/v1/intake/sessions", {
    method: "POST",
    body: JSON.stringify({ lang, project_id: projectId })
  });
}

// Feed the Classification Service's terminal PML payload into the declared/gap
// side. The raw partner payload is forwarded verbatim; the intake service maps
// it at the boundary (adapt_pml) and writes it ONLY to declared_stage — it never
// enters the evidence ledger, gates, or question selection.
export function applyPml(sessionId: string, payload: Record<string, unknown>) {
  return request<SessionState>(`/api/v1/intake/sessions/${sessionId}/pml`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function answerSession(sessionId: string, questionId: string, rawAnswer: string) {
  return request<AnswerResult>(`/api/v1/intake/sessions/${sessionId}/answers`, {
    method: "POST",
    body: JSON.stringify({ question_id: questionId, raw_answer: rawAnswer })
  });
}

export function getSessionState(sessionId: string) {
  return request<SessionState>(`/api/v1/intake/sessions/${sessionId}/state`);
}

export function getDiagnosis(sessionId: string) {
  return request<Diagnosis>(`/api/v1/intake/sessions/${sessionId}/diagnosis`);
}

export function resumeSession(sessionId: string) {
  return request<AnswerResult>(`/api/v1/intake/sessions/${sessionId}/resume`, {
    method: "POST"
  });
}
