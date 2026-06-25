import type { DemoBlocker, DashboardAnalysis, GeneratedRoadmapAction, Resource } from "../api/types";

/** The 6-stage maturity taxonomy, in order (S1 → S6). */
export const STAGE_ORDER = [
  "IDEATION",
  "MARKET_VALIDATION",
  "STRUCTURATION",
  "FUNDRAISING",
  "LAUNCH_PLANNING",
  "GROWTH"
] as const;

export type Stage = (typeof STAGE_ORDER)[number];

export function stageIndex(stage: string | undefined | null): number {
  if (!stage) return -1;
  return STAGE_ORDER.indexOf(stage as Stage);
}

/** Canonical order of the five explainable scores. */
export const SCORE_KEYS = [
  "market_score",
  "commercial_offer_score",
  "innovation_score",
  "scalability_score",
  "green_score"
] as const;

export type ScoreKey = (typeof SCORE_KEYS)[number];

/** Stable ordering: known scores first (canonical order), then any extras. */
export function orderedScores(scores: Record<string, number>): Array<[string, number]> {
  const known = SCORE_KEYS.filter((key) => key in scores).map((key) => [key, scores[key]] as [string, number]);
  const extra = Object.entries(scores).filter(([key]) => !SCORE_KEYS.includes(key as ScoreKey));
  return [...known, ...extra];
}

/** The weakest score — the one weakest-link aggregation pins the verdict to. */
export function weakestScore(scores: Record<string, number>): string | null {
  const entries = Object.entries(scores);
  if (entries.length === 0) return null;
  return entries.reduce((min, current) => (current[1] < min[1] ? current : min))[0];
}

export type GapTone = "evidence" | "caution" | "flag";

/** Maps a gap level to its semantic tone. Red is reserved for real divergence. */
export function gapTone(gapLevel: string | undefined): GapTone {
  switch ((gapLevel ?? "").toUpperCase()) {
    case "NONE":
    case "LOW":
      return "evidence";
    case "MEDIUM":
      return "caution";
    case "HIGH":
    case "CRITICAL":
      return "flag";
    default:
      return "caution";
  }
}

export function scoreTone(value: number): GapTone {
  if (value >= 60) return "evidence";
  if (value >= 45) return "caution";
  return "flag";
}

/** Confidence below this renders as "provisional". */
export const PROVISIONAL_CONFIDENCE = 0.65;

/**
 * The causal chain for one diagnosed gap:
 *   blocker → score(s) it dragged down → cited program(s) → the roadmap fix.
 * Every hop is reconstructed from real link fields; `fix` is null when no
 * roadmap has been generated yet (graceful partial state).
 */
export type CausalChain = {
  blocker: DemoBlocker;
  scores: string[];
  resources: Resource[];
  sources: string[];
  fix: GeneratedRoadmapAction | null;
};

export function buildCausalChain(analysis: DashboardAnalysis, blocker: DemoBlocker): CausalChain {
  const actions = analysis.roadmap?.actions ?? [];
  const fix = actions.find((action) => action.addresses_blockers.includes(blocker.id)) ?? null;
  const resourceById = new Map(analysis.resources.map((resource) => [resource.resource_id, resource]));

  const resourceIds = fix?.resource_ids ?? [];
  const resources = resourceIds.map((id) => resourceById.get(id)).filter((item): item is Resource => Boolean(item));

  // Scores this gap dragged down: prefer the fix's improves_scores; otherwise
  // fall back to the score whose weak sub-scores name the recommended action.
  let scores = fix?.improves_scores ?? [];
  if (scores.length === 0 && blocker.recommended_action_key) {
    scores = Object.entries(analysis.score_details)
      .filter(([, detail]) => detail.weak_sub_scores.includes(blocker.recommended_action_key as string))
      .map(([score]) => score);
  }

  return { blocker, scores, resources, sources: fix?.source_urls ?? [], fix };
}

/**
 * The chain for a single score: what dragged it down, and the program that lifts it.
 * Keyed on the score (the weakest-link story) rather than a blocker.
 */
export type ScoreChain = {
  weakSubScores: string[];
  resources: Resource[];
  sources: string[];
  fix: GeneratedRoadmapAction | null;
};

export function buildScoreChain(analysis: DashboardAnalysis, scoreKey: string): ScoreChain {
  const actions = analysis.roadmap?.actions ?? [];
  const fix = actions.find((action) => action.improves_scores.includes(scoreKey)) ?? null;
  const resourceById = new Map(analysis.resources.map((resource) => [resource.resource_id, resource]));
  const resources = (fix?.resource_ids ?? [])
    .map((id) => resourceById.get(id))
    .filter((item): item is Resource => Boolean(item));
  return {
    weakSubScores: analysis.score_details[scoreKey]?.weak_sub_scores ?? [],
    resources,
    sources: fix?.source_urls ?? [],
    fix
  };
}

/** Diagnosed gaps, stage-blocking first, then by priority rank. */
export function orderedBlockers(blockers: DemoBlocker[]): DemoBlocker[] {
  return [...blockers].sort((a, b) => {
    if (a.stage_blocking !== b.stage_blocking) return a.stage_blocking ? -1 : 1;
    return a.priority_rank - b.priority_rank;
  });
}
