from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from shared.contracts.enums import (
    ActionStatus,
    ActorType,
    BlockerType,
    BusinessType,
    CountryCode,
    EligibilityStatus,
    GapLevel,
    MaturityStage,
    QuestionType,
    RoadmapHorizon,
    Severity,
    TenderReadinessStatus,
    EvidenceStatus, 
)


class ContractModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")


class EvidenceItem(ContractModel):
    field: str
    value: Any
    impact: str
    rule_id: str | None = None


class Question(ContractModel):
    id: str
    code: str
    text: dict[str, str]
    type: QuestionType
    required: bool = True
    depends_on: list[str] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    options: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class IntakeSession(ContractModel):
    session_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    asked_question_codes: list[str] = Field(default_factory=list)
    completed: bool = False
    next_question: Question | None = None
    activated_probes: list[str] = Field(default_factory=list)


class IntakeAnswerRequest(ContractModel):
    session_id: UUID | None = None
    question_code: str
    value: Any


class IntakeAnswerResponse(ContractModel):
    session: IntakeSession
    profile_patch: dict[str, Any] = Field(default_factory=dict)
    missing_required_fields: list[str] = Field(default_factory=list)


class EvidenceEntry(BaseModel):
    """
    One row of the evidence_ledger. Keyed by field name in
    ProjectProfile.evidence_ledger: dict[str, EvidenceEntry].
 
    The Adaptive Intake Engine is the only service that WRITES this.
    The Scoring Service only READS it — scoring never re-asks the
    founder for something intake already tagged.
    """
    model_config = ConfigDict(use_enum_values=True, extra="forbid")
 
    status: EvidenceStatus = EvidenceStatus.UNVERIFIED
    source: str | None = None          # e.g. "uploaded_invoice", "rne_extract", "self_declared"
    note: str | None = None            # free-text trace for the audit log

class ProjectCreateRequest(ContractModel):
    country: CountryCode = CountryCode.TN
    region: str | None = None
    actor_type: ActorType = ActorType.ENTREPRENEUR
    business_type: BusinessType = BusinessType.STARTUP
    sector: str = "technology"
    sub_sector: str | None = "saas"
    declared_stage: MaturityStage = MaturityStage.FUNDRAISING
    primary_goal: str = "funding"


class ProjectProfile(ContractModel):
    project_id: UUID = Field(default_factory=uuid4)
    country: CountryCode = CountryCode.TN
    region: str | None = None
    actor_type: ActorType = ActorType.ENTREPRENEUR
    business_type: BusinessType = BusinessType.STARTUP
    sector: str | None = "technology"
    sub_sector: str | None = None
    declared_stage: MaturityStage = MaturityStage.IDEATION
    primary_goal: str | None = None
    legal_form: str | None = None
    formalization_status: str | None = None
    team_size: int | None = None
    years_active: int | None = None
    has_mvp: bool | None = None
    has_revenue: bool | None = None
    monthly_revenue: float | None = None
    recurring_revenue: bool | None = None
    paying_customers: int | None = None
    documented_interviews: int | None = None
    market_validation_evidence: list[str] = Field(default_factory=list)
    market_size_known: bool | None = None
    competition_understanding: int | None = Field(default=None, ge=0, le=100)
    revenue_model_clarity: int | None = Field(default=None, ge=0, le=100)
    innovation_level: int | None = Field(default=None, ge=0, le=100)
    process_automation_level: float | None = Field(default=None, ge=0, le=1)
    green_practices: list[str] = Field(default_factory=list)
    wants_public_tenders: bool | None = None
    administrative_documents_ready: bool | None = None
    financial_capacity_score: int | None = Field(default=None, ge=0, le=100)
    tender_references_count: int | None = Field(default=None, ge=0)
    export_interest: bool | None = None
    funding_need: bool | None = None
    extra_answers: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    evidence_ledger: dict[str, EvidenceEntry] = Field(default_factory=dict)
    tech_stack_scalability: int | None = Field(default=None, ge=0, le=100)
    infrastructure_readiness: int | None = Field(default=None, ge=0, le=100)
    problem_novelty_score: int | None = Field(default=None, ge=0, le=100)
    ip_assets: list[str] = Field(default_factory=list)
    rd_investment_ratio: float | None = Field(default=None, ge=0, le=1)
    technology_readiness_level: int | None = Field(default=None, ge=1, le=9)
    process_documentation_score: int | None = Field(default=None, ge=0, le=100)
    financial_model_quality: int | None = Field(default=None, ge=0, le=100)
    legal_compliance_score: int | None = Field(default=None, ge=0, le=100)
    climate_air_impact_score: int | None = Field(default=None, ge=0, le=100)
    water_impact_score: int | None = Field(default=None, ge=0, le=100)
    soil_biodiversity_score: int | None = Field(default=None, ge=0, le=100)
    resources_waste_score: int | None = Field(default=None, ge=0, le=100)
    sdg_alignment_score: int | None = Field(default=None, ge=0, le=100)


class MaturityPrediction(ContractModel):
    diagnosed_stage: MaturityStage
    declared_stage: MaturityStage
    gap_level: GapLevel
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    triggered_rules: list[str] = Field(default_factory=list)
    model_version: str = "rules-v0.1.0"


class SubScore(ContractModel):
    name: str
    value: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    contribution: float
    fundamental: bool = False


class Score(ContractModel):
    name: str
    value: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    sub_scores: list[SubScore] = Field(default_factory=list)
    missing_criteria: list[str] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    highest_leverage_action: str
    triggered_rules: list[str] = Field(default_factory=list)
    version: str


class CompositeScores(ContractModel):
    scores: list[Score]
    version: str = "weighted-rules-v0.1.0"

    def by_name(self) -> dict[str, Score]:
        scores: dict[str, Score] = {}
        aliases = {
            "Market Score": "market_score",
            "Operational Score": "operational_score",
            "Commercial Offer Score": "commercial_offer_score",
            "Innovation Score": "innovation_score",
            "Scalability Score": "scalability_score",
            "Green Score": "green_score",
        }
        for score in self.scores:
            scores[score.name] = score
            scores[aliases.get(score.name, score.name)] = score
        return scores


class Blocker(ContractModel):
    id: str = Field(default_factory=lambda: f"blocker-{uuid4().hex[:8]}")
    type: BlockerType
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    priority: int
    evidence: list[str] = Field(default_factory=list)
    is_missing_information: bool = False
    related_stage: MaturityStage


class BlockerResult(ContractModel):
    blockers: list[Blocker]
    model_version: str = "rules-v0.1.0"


class ConfidenceReport(ContractModel):
    overall_confidence: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[str] = Field(default_factory=list)
    manual_review_required: bool = False


class ResourceMatch(ContractModel):
    resource_id: str
    name: str
    institution: str
    country: CountryCode
    type: str
    relevance_score: float = Field(ge=0, le=1)
    source_url: str
    source_chunk_ids: list[str] = Field(default_factory=list)
    matched_reasons: list[str] = Field(default_factory=list)
    eligible_stages: list[MaturityStage] = Field(default_factory=list)
    eligibility_conditions: list[dict[str, Any]] = Field(default_factory=list)
    synthetic: bool = True


class EligibilityResult(ContractModel):
    resource_id: str
    status: EligibilityStatus
    matched_conditions: list[str] = Field(default_factory=list)
    failed_conditions: list[str] = Field(default_factory=list)
    missing_conditions: list[str] = Field(default_factory=list)


class RoadmapAction(ContractModel):
    id: str
    title: str
    horizon: RoadmapHorizon
    priority: int
    rationale: str
    addresses_blocker_ids: list[str] = Field(default_factory=list)
    addresses_score: str | None = None
    resource_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    status: ActionStatus = ActionStatus.TODO


class Roadmap(ContractModel):
    roadmap_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    actions: list[RoadmapAction]


class TenderProbeResult(ContractModel):
    status: TenderReadinessStatus
    score: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class ProgressEvent(ContractModel):
    event_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    action_id: str
    event_type: str = "ACTION_COMPLETED"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AnalysisResult(ContractModel):
    project_id: UUID
    profile: ProjectProfile
    maturity: MaturityPrediction
    scores: CompositeScores
    blockers: BlockerResult
    confidence: ConfidenceReport
    resources: list[ResourceMatch]
    eligibility: list[EligibilityResult]
    roadmap: Roadmap
    explanations: dict[str, str] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DashboardResponse(ContractModel):
    project_id: UUID
    profile: ProjectProfile
    analysis: AnalysisResult | None = None
    progress_events: list[ProgressEvent] = Field(default_factory=list)

@property
def effective_stage(self) -> MaturityStage:
    return (
        self.maturity_prediction.diagnosed_stage
        if self.maturity_prediction
        else self.declared_stage
    )

# ---------------------------------------------
# Startup classifier contract (frontend/API)
# ---------------------------------------------


class StartupOptionPayload(ContractModel):
    index: int
    text: str


class StartupTranscriptEntry(ContractModel):
    node_id: str
    question: str
    chosen_answer_text: str


class StartupQuestionPayload(ContractModel):
    session_industry_key: str
    session_id: str | None = None
    node_id: str
    phase: str | None = None
    dimension: str | None = None
    question: str
    explanation: str | None = None
    allow_free_text: bool = False
    options: list[StartupOptionPayload] = Field(default_factory=list)
    is_terminal: bool = False


class StartupResultPayload(ContractModel):
    session_industry_key: str
    node_id: str
    phase: str
    result_text: str
    transcript: list[StartupTranscriptEntry] = Field(default_factory=list)
    is_terminal: bool = True


class StartupStartRequest(ContractModel):
    industry_key: str


class StartupAnswerRequest(ContractModel):
    session_industry_key: str
    session_id: str | None = None
    node_id: str
    selected_option_index: int | None = None
    free_text: str | None = None
    transcript_so_far: list[StartupTranscriptEntry] = Field(default_factory=list)
