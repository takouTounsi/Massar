// Client for the Classification Service (the founder's PERCEIVED maturity / PML).
// A branching questionnaire: pick an industry, describe the company (free text),
// then answer option questions until a terminal `phase`. That terminal payload is
// the founder's self-assessment — it is fed to the intake engine ONLY via the
// /pml endpoint (declared/perceived side), never into the evidence ledger.

import { request } from "./client";

export type Industry = { key: string; name: string; family: string };

export type ClassifierOption = { index: number; text: string };

export type ClassifierTranscriptEntry = {
  node_id: string;
  question: string;
  chosen_answer_text: string;
};

// A turn is either a next question (is_terminal=false) or the terminal result
// (is_terminal=true) that carries the PML `phase`. Both share these fields.
export type ClassifierStep = {
  session_industry_key: string;
  session_id?: string | null;
  node_id: string;
  phase?: string | null;
  dimension?: string | null;
  question?: string;
  explanation?: string | null;
  allow_free_text?: boolean;
  options?: ClassifierOption[];
  is_terminal: boolean;
  // Present on the terminal step:
  result_text?: string;
  transcript?: ClassifierTranscriptEntry[];
};

export function listIndustries() {
  return request<Industry[]>("/api/v1/classification/industries");
}

export function startClassification(industryKey: string) {
  return request<ClassifierStep>("/api/v1/classification/session/start", {
    method: "POST",
    body: JSON.stringify({ industry_key: industryKey })
  });
}

export function answerClassification(payload: {
  session_industry_key: string;
  session_id?: string | null;
  node_id: string;
  selected_option_index?: number | null;
  free_text?: string | null;
  transcript_so_far: ClassifierTranscriptEntry[];
}) {
  return request<ClassifierStep>("/api/v1/classification/session/answer", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
