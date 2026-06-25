export type User = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  two_factor_enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type AuthResponse = {
  access_token?: string | null;
  refresh_token?: string | null;
  token_type: "bearer";
  expires_in?: number | null;
  requires_2fa: boolean;
  temporary_login_token?: string | null;
  user?: User | null;
};

export type ProjectProfile = {
  project_id: string;
  name?: string;
  country: "TN" | "MA" | "DZ";
  region?: string;
  business_type: "startup" | "traditional_business";
  sector?: string;
  declared_stage: string;
  primary_goal?: string;
  synthetic?: boolean;
};

export type IntakeSession = {
  session_id: string;
  project_id: string;
  completed: boolean;
  asked_question_codes?: string[];
  next_question?: {
    code: string;
    text: Record<string, string>;
    type: string;
    options: string[];
    tags?: string[];
  } | null;
};

export type EvidenceAttachment = {
  evidence_id: string;
  project_id: string;
  session_id?: string | null;
  question_code?: string | null;
  filename: string;
  content_type: string;
  size: number;
  uploaded_at: string;
};

export type DemoScoreMap = Record<string, number>;

export type DemoBlocker = {
  id: string;
  type: string;
  severity: string;
  priority_rank: number;
  stage_blocking: boolean;
  recommended_action_key?: string;
  evidence: string[];
};

export type Resource = {
  resource_id: string;
  name: string;
  institution: string;
  country: string;
  category: string;
  eligibility_status: string;
  source_url: string;
  matched_reasons: string[];
  synthetic: boolean;
};

export type GeneratedRoadmapAction = {
  id: string;
  title: string;
  description: string;
  horizon: string;
  priority: number;
  status: string;
  estimated_effort: string;
  addresses_blockers: string[];
  improves_scores: string[];
  depends_on: string[];
  evidence: string[];
  resource_ids: string[];
  reason: string;
  source_urls: string[];
};

export type GeneratedRoadmap = {
  roadmap_id: string;
  project_id: string;
  generated_at: string;
  roadmap_version: string;
  summary: {
    current_focus: string;
    next_stage_target: string;
    confidence: number;
  };
  actions: GeneratedRoadmapAction[];
  missing_information_actions: Array<{ field: string; reason: string }>;
};

export type DemoDashboard = {
  // Demo path returns `project`; the real profile-service path returns `profile`.
  project?: ProjectProfile;
  profile?: ProjectProfile;
  // Null on a freshly created project that has no diagnosis yet (intake not run).
  analysis: {
    diagnosed_stage: string;
    declared_stage: string;
    gap_level: string;
    maturity_confidence: number;
    scores: DemoScoreMap;
    score_details: Record<string, { weak_sub_scores: string[] }>;
    blockers: DemoBlocker[];
    resources: Resource[];
    missing_fields: string[];
    progress: number;
    roadmap?: GeneratedRoadmap;
  } | null;
};

/** The diagnosis payload once it exists — non-null. Pages guard on the null
 * case (fresh project) and pass this down, so downstream consumers never see null. */
export type DashboardAnalysis = NonNullable<DemoDashboard["analysis"]>;

export type LegacyDashboard = {
  project_id: string;
  profile: ProjectProfile;
  progress_events: Array<{ event_id: string; action_id: string; created_at: string }>;
  analysis?: unknown;
};
