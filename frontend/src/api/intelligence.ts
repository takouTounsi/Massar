/**
 * TypeScript mirror of the deterministic intelligence layer defined in
 * `shared/domain/scoring_intelligence.py` on the `scoring_module` branch.
 *
 * The live API on this branch returns the slim `DemoDashboard`; these types
 * describe the richer `IntelligenceReport` the Scores / Intelligence pages are
 * built to render. Components accept these as OPTIONAL and degrade gracefully
 * to `DemoDashboard`-derived values (see `lib/intelligence.ts`) when absent —
 * we never fabricate engine numbers, we label derived ones as estimates.
 */

/** Default weakest-link penalty coefficient (LAMBDA_DEFAULT in scoring.py). */
export const LAMBDA_DEFAULT = 0.5;

/** Readiness dimension weights — must mirror _READINESS_WEIGHTS. */
export const READINESS_WEIGHTS: Record<string, number> = {
  "Market Score": 0.3,
  "Operational Score": 0.25,
  "Scalability Score": 0.2,
  "Innovation Score": 0.15,
  "Green Score": 0.1
};

export type CriterionContribution = {
  criterion_name: string;
  weight: number;
  raw_value: number;
  weighted_contribution: number;
  is_fundamental: boolean;
  lambda_penalty_exposure: number;
  evidence_status: string;
  evidence_cost: number;
  is_weakest_fundamental: boolean;
};

export type ScoreDecomposition = {
  score_name: string;
  composite_value: number;
  c_base: number;
  lambda_penalty_cost: number;
  lambda_penalty_fraction: number;
  weakest_fundamental_criterion: string | null;
  weakest_fundamental_value: number | null;
  criterion_contributions: CriterionContribution[];
  anomaly_penalties: string[];
  anomaly_confidence_cost: number;
  top_reduction_causes: string[];
  missing_evidence_cost: number;
  confidence_value: number;
};

export type ReadinessContribution = {
  dimension: string;
  raw_score: number;
  weight: number;
  confidence: number;
  confidence_adjusted_score: number;
  dependency_multiplier: number;
  effective_score: number;
  weighted_contribution: number;
};

export type ReadinessReport = {
  overall_readiness: number;
  readiness_without_penalty: number;
  confidence_adjusted_readiness: number;
  bottleneck_cost: number;
  weakest_link_floor: number;
  contributions: ReadinessContribution[];
  formula_trace: string;
};

export type BottleneckAnalysis = {
  bottleneck_node_id: string;
  bottleneck_type: string;
  blocked_potential: number;
  explanation: string;
  improving_others_first_explanation: string;
};

export type ScoreDelta = {
  score_name: string;
  before: number;
  after: number;
  delta: number;
  confidence_before: number;
  confidence_after: number;
  confidence_delta: number;
};

export type CounterfactualResult = {
  action_id: string;
  action_title: string;
  effort: number;
  score_deltas: ScoreDelta[];
  overall_readiness_before: number;
  overall_readiness_after: number;
  overall_readiness_gain: number;
  leverage: number;
  sector: string;
  stage: string;
  contextual_notes: string[];
};

export type ConfidenceSignal = {
  score_name: string;
  current_score: number;
  current_confidence: number;
  criterion_name: string;
  criterion_weight: number;
  upload_action: string;
  expected_confidence_gain: number;
};

export type BoardSummary = {
  executive_summary: string;
  key_risk: string;
  main_opportunity: string;
  strategic_focus: string;
  generated_by: string;
};
