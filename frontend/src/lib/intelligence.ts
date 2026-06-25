import type { DashboardAnalysis } from "../api/types";
import type { GeneratedRoadmapAction } from "../api/types";
import { LAMBDA_DEFAULT } from "../api/intelligence";
import { weakestScore } from "./diagnosis";

const EFFORT_WEEKS: Record<string, number> = {
  TRIVIAL: 0.5,
  LOW: 1.5,
  MEDIUM: 3,
  HIGH: 6,
  VERY_HIGH: 12
};

/**
 * Readiness figures derived from the live scores, shaped to mirror the engine's
 * `ReadinessReport`. `overall` blends the mean with the weakest link (a stand-in
 * for the dependency-aware, weakest-link-floored composite); `bottleneckCost` is
 * what the weakest link costs versus a naive average. Estimates — label them.
 */
export function deriveReadiness(analysis: DashboardAnalysis) {
  const values = Object.values(analysis.scores);
  if (values.length === 0) {
    return { overall: 0, withoutPenalty: 0, bottleneckCost: 0, weakestFloor: 0, weakest: null as string | null };
  }
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const floor = Math.min(...values);
  const overall = mean * 0.6 + floor * 0.4; // weakest-link drag
  return {
    overall: Math.round(overall * 10) / 10,
    withoutPenalty: Math.round(mean * 10) / 10,
    bottleneckCost: Math.round((overall - mean) * 10) / 10,
    weakestFloor: Math.round(floor * 10) / 10,
    weakest: weakestScore(analysis.scores)
  };
}

export type ActionLeverage = {
  action: GeneratedRoadmapAction;
  gain: number;
  effort: number;
  leverage: number;
};

/** Ranks roadmap actions by projected readiness gain per founder-week of effort. */
export function rankActionLeverage(
  analysis: DashboardAnalysis,
  actions: GeneratedRoadmapAction[]
): ActionLeverage[] {
  return actions
    .map((action) => {
      const { readinessGain } = projectActionImpact(analysis.scores, action.improves_scores, action.estimated_effort);
      const effort = EFFORT_WEEKS[(action.estimated_effort ?? "").toUpperCase()] ?? 2;
      const leverage = Math.round((readinessGain / effort) * 10) / 10;
      return { action, gain: readinessGain, effort, leverage };
    })
    .filter((row) => row.gain > 0)
    .sort((a, b) => b.leverage - a.leverage);
}

/**
 * Best-effort λ-penalty figures derived from the documented weakest-link rule
 * when the real `ScoreDecomposition` isn't wired into the API.
 *
 * The engine computes  C = C_base · (1 − λ · (1 − x_min))  with λ = 0.5.
 * A score is flagged "penalized" only when it has a weak fundamental sub-score;
 * for that case we treat x_min ≈ 0 (the criterion is the one dragging it down),
 * which makes the factor (1 − λ) and lets us invert C_base = C / (1 − λ).
 *
 * Everything returned here is an ESTIMATE — callers must label it as such.
 */
export type LambdaEstimate = {
  /** true when a weak fundamental sub-score makes the penalty meaningful */
  penalized: boolean;
  composite: number;
  /** estimated pre-penalty base */
  cBase: number;
  factor: number;
  lambda: number;
  /** the weak sub-score names that expose the penalty */
  causes: string[];
};

/**
 * Transparent projection of a roadmap action's impact, used by the
 * counterfactual hover when the real `CounterfactualResult` isn't wired.
 *
 * Gain per improved score scales with the headroom to a healthy 75 and the
 * action's effort weight — i.e. cheap actions on weak scores read as high
 * leverage. Strictly an ESTIMATE; callers must label it.
 */
export type ProjectedDelta = { score: string; before: number; after: number; delta: number };

const EFFORT_FACTOR: Record<string, number> = {
  TRIVIAL: 0.4,
  LOW: 0.6,
  MEDIUM: 0.8,
  HIGH: 1,
  VERY_HIGH: 1
};

export function projectActionImpact(
  scores: Record<string, number>,
  improvesScores: string[],
  estimatedEffort?: string
): { deltas: ProjectedDelta[]; readinessGain: number } {
  const factor = EFFORT_FACTOR[(estimatedEffort ?? "").toUpperCase()] ?? 0.7;
  const deltas: ProjectedDelta[] = improvesScores
    .filter((s) => s in scores)
    .map((score) => {
      const before = Math.round(scores[score]);
      const headroom = Math.max(0, 75 - before);
      const delta = Math.max(2, Math.round(headroom * 0.35 * factor));
      return { score, before, after: Math.min(100, before + delta), delta };
    });
  const readinessGain = deltas.length > 0 ? Math.round((deltas.reduce((s, d) => s + d.delta, 0) / deltas.length) * 0.3 * 10) / 10 : 0;
  return { deltas, readinessGain };
}

export function estimateLambda(analysis: DashboardAnalysis, scoreKey: string): LambdaEstimate {
  const composite = Math.round(analysis.scores[scoreKey] ?? 0);
  const causes = analysis.score_details[scoreKey]?.weak_sub_scores ?? [];
  const isWeakest = weakestScore(analysis.scores) === scoreKey;
  const penalized = isWeakest && causes.length > 0;
  const factor = penalized ? 1 - LAMBDA_DEFAULT : 1;
  const cBase = factor > 0 ? Math.min(100, Math.round(composite / factor)) : composite;
  return { penalized, composite, cBase, factor, lambda: LAMBDA_DEFAULT, causes };
}
