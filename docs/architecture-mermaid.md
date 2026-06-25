# Architecture Mermaid detaillee

Ce document decrit l'architecture du projet Massar avec Mermaid. Il complete
`ARCHITECTURE.md`, `docs/architecture.md`, `docs/domain-model.md` et
`docs/data-model.md` avec une vue plus orientee classes.

Les sources principales utilisees sont:

- `frontend/src/main.tsx`, `frontend/src/components/AppLayout.tsx`,
  `frontend/src/api/*`, `frontend/src/hooks/*`
- `services/*/app/main.py`
- `shared/contracts/schemas.py`, `shared/contracts/enums.py`
- `shared/domain/*`
- `shared/intake/*`
- `shared/application/orientation_pipeline.py`
- `shared/database/models.py`
- `shared/database/migrations/versions/0001_initial.py`

## 1. Vue globale conteneurs

```mermaid
flowchart LR
    U[Utilisateur entrepreneur] --> FE[Frontend React / Vite]
    FE -->|HTTP + Bearer token + cookie refresh| GW[API Gateway FastAPI]

    subgraph Gateway["services/api_gateway"]
        GW --> AUTH[Auth module]
        GW --> ORCH[Orchestration HTTP]
        GW --> DEMO[Demo data provider]
        GW --> ROADMAP_GEN[Roadmap demo integration]
    end

    ORCH --> INTAKE[Intake Service]
    ORCH --> CLASSIF[Classification Service / PML]
    ORCH --> PROFILE[Profile Service]
    ORCH --> MATURITY[Maturity Service]
    ORCH --> SCORING[Scoring Service]
    ORCH --> BLOCKERS[Blocker Service]
    ORCH --> CONF[Confidence Service]
    ORCH --> RESOURCE[Resource Service]
    ORCH --> ELIG[Eligibility Service]
    ORCH --> ROADMAP[Roadmap Service]
    ORCH --> PROGRESS[Progress Service]
    ORCH -. optional .-> EXPLAIN[Explainability Service]
    ORCH -. secondary .-> ASSIST[Assistant Service]

    INTAKE --> SHARED_INTAKE[shared/intake]
    MATURITY --> DOMAIN[shared/domain]
    SCORING --> DOMAIN
    BLOCKERS --> DOMAIN
    CONF --> DOMAIN
    RESOURCE --> DOMAIN
    ELIG --> DOMAIN
    ROADMAP --> DOMAIN
    PROFILE --> PIPELINE[InMemoryOrientationPipeline]
    PIPELINE --> DOMAIN

    PROFILE --> DB[(PostgreSQL + JSONB)]
    RESOURCE --> KB[(Synthetic knowledge base)]
    ROADMAP --> TPL[(roadmap_templates.json)]
    INTAKE --> REDIS[(Redis optional sessions)]
    INGEST[Knowledge Ingestion Service] --> KB
    EVAL[Evaluation Service] --> ART[(artifacts/evaluation)]
```

## 2. Vue packages / responsabilites

```mermaid
flowchart TB
    subgraph Frontend["frontend/src"]
        ROUTES[main.tsx routes]
        LAYOUT[AppLayout]
        PAGES[pages]
        HOOKS[hooks]
        APITS[api clients + TS types]
        I18N[i18n FR/AR]
        ROUTES --> LAYOUT --> PAGES
        PAGES --> HOOKS --> APITS
        PAGES --> I18N
    end

    subgraph Services["services"]
        API[api_gateway]
        INTAKE_S[intake_service]
        CLASS_S[classification_service]
        PROFILE_S[profile_service]
        CORE_S[maturity/scoring/blocker/confidence/resource/eligibility]
        ROADMAP_S[roadmap_service]
        PROGRESS_S[progress_service]
        AUX_S[assistant/explainability/knowledge/evaluation]
    end

    subgraph Shared["shared"]
        CONTRACTS[contracts: Pydantic DTOs + enums]
        DOMAIN[domain: rules, scoring, maturity, roadmap]
        ADAPTIVE[intake: ledger-driven engine]
        APP[application: local pipeline + classifier router]
        DB[database: SQLAlchemy + Alembic]
        SECURITY[security: tokens support, encryption, leases]
        DEMODATA[demo_data provider]
    end

    subgraph RulesModels["rules / models / data"]
        RULES[rules YAML]
        REGISTRY[models/registry.json]
        KB[data knowledge base]
        DEMOJSON[shared/demo_data JSON]
    end

    Frontend --> API
    API --> Services
    Services --> Shared
    DOMAIN --> RULES
    DOMAIN --> REGISTRY
    RESOURCE_S --> KB
    API --> DEMOJSON
```

## 3. Flux principal d'analyse

Endpoint public principal: `POST /api/v1/projects/{project_id}/analysis/run`.

```mermaid
sequenceDiagram
    autonumber
    participant FE as Frontend
    participant GW as API Gateway
    participant AUTH as AuthService
    participant P as Profile Service
    participant M as Maturity Service
    participant S as Scoring Service
    participant B as Blocker Service
    participant C as Confidence Service
    participant R as Resource Service
    participant E as Eligibility Service
    participant RM as Roadmap Service

    FE->>GW: POST /analysis/run
    GW->>AUTH: require_user(access_token)
    AUTH-->>GW: UserPublic
    GW->>P: GET /profiles/projects/{id}
    P-->>GW: ProjectProfile
    GW->>M: POST /maturity/predict
    M-->>GW: MaturityPrediction
    GW->>S: POST /scores/calculate
    S-->>GW: CompositeScores
    GW->>B: POST /blockers/detect
    B-->>GW: BlockerResult
    GW->>C: POST /confidence/assess
    C-->>GW: ConfidenceReport
    GW->>R: POST /resources/match
    R-->>GW: ResourceMatch[]
    GW->>E: POST /eligibility/check
    E-->>GW: EligibilityResult[]
    GW->>RM: POST /roadmaps/build
    RM-->>GW: Roadmap
    GW->>P: POST /profiles/projects/{id}/analysis
    P-->>GW: AnalysisResult saved
    GW-->>FE: AnalysisResult
```

## 4. Flux intake adaptatif + PML

Le projet contient deux intakes:

- legacy: `AdaptiveIntakeEngine` dans `shared/domain/intake.py`
- adaptatif principal: `IntakeEngine` dans `shared/intake/engine.py`

Le PML vient du `classification_service`; il alimente seulement le cote
`declared_stage` / perception. Il ne modifie pas le ledger de preuves.

```mermaid
sequenceDiagram
    autonumber
    participant FE as ProjectIntakeFlow
    participant GW as API Gateway
    participant CL as Classification Service
    participant IN as Intake Service
    participant IE as IntakeEngine
    participant EX as Extractor
    participant DIAG as build_diagnosis
    participant MAT as LedgerMaturityPredictor
    participant SCORE as WeightedRuleScoreCalculator

    FE->>GW: GET /classification/industries
    GW->>CL: GET /api/v1/startup/industries
    CL-->>GW: Industry[]
    GW-->>FE: Industry[]

    FE->>GW: POST /classification/session/start
    GW->>CL: start PML tree
    CL-->>GW: StartupQuestionPayload
    GW-->>FE: question

    FE->>GW: POST /classification/session/answer
    GW->>CL: route option/free text
    CL-->>GW: StartupResultPayload or next question
    GW-->>FE: PML result

    FE->>GW: POST /intake/sessions
    GW->>IN: POST /sessions
    IN->>IE: start_session()
    IE-->>IN: IntakeState + first question
    IN-->>GW: SessionStartResponse
    GW-->>FE: first question

    FE->>GW: POST /intake/sessions/{id}/pml
    GW->>IN: POST /sessions/{id}/pml
    IN->>IE: apply_pml()
    IE-->>IN: StateResponse
    IN-->>GW: StateResponse
    GW-->>FE: declared stage state

    loop answers
        FE->>GW: POST /intake/sessions/{id}/answers
        GW->>IN: raw_answer + question_id
        IN->>IE: process_answer()
        IE->>EX: extract scoped fields
        EX-->>IE: ExtractionResult
        IE-->>IN: AnswerResponse
        IN-->>GW: next_question or diagnostic_ready
        GW-->>FE: AnswerResponse
    end

    FE->>GW: GET /intake/sessions/{id}/diagnosis
    GW->>IN: GET /sessions/{id}/diagnosis
    IN->>DIAG: build_diagnosis(IntakeState)
    DIAG->>MAT: predict(ledger, declared_stage)
    DIAG->>SCORE: calculate_with_ledger(profile, ledger)
    DIAG-->>IN: DiagnosisResponse
    IN-->>GW: DiagnosisResponse
    GW-->>FE: DiagnosisResponse
```

## 5. Diagramme de classes principal: contrats metier

Source: `shared/contracts/schemas.py` et `shared/contracts/enums.py`.

```mermaid
classDiagram
direction LR

class ContractModel {
  <<Pydantic>>
  +ConfigDict model_config
}

class ProjectCreateRequest {
  +CountryCode country
  +str region
  +ActorType actor_type
  +BusinessType business_type
  +str sector
  +str sub_sector
  +MaturityStage declared_stage
  +str primary_goal
}

class ProjectProfile {
  +UUID project_id
  +CountryCode country
  +str region
  +ActorType actor_type
  +BusinessType business_type
  +str sector
  +str sub_sector
  +MaturityStage declared_stage
  +str primary_goal
  +str legal_form
  +str formalization_status
  +int team_size
  +int years_active
  +bool has_mvp
  +bool has_revenue
  +float monthly_revenue
  +bool recurring_revenue
  +int paying_customers
  +int documented_interviews
  +list~str~ market_validation_evidence
  +bool market_size_known
  +int competition_understanding
  +int revenue_model_clarity
  +int innovation_level
  +float process_automation_level
  +list~str~ green_practices
  +bool wants_public_tenders
  +bool administrative_documents_ready
  +int financial_capacity_score
  +int tender_references_count
  +dict~str, Any~ extra_answers
  +dict~str, EvidenceEntry~ evidence_ledger
  +int version
}

class EvidenceEntry {
  +EvidenceStatus status
  +str source
  +str note
}

class EvidenceItem {
  +str field
  +Any value
  +str impact
  +str rule_id
}

class Question {
  +str id
  +str code
  +dict~str, str~ text
  +QuestionType type
  +bool required
  +list~str~ depends_on
  +dict validation
  +list~str~ options
  +list~str~ tags
}

class IntakeSession {
  +UUID session_id
  +UUID project_id
  +list~str~ asked_question_codes
  +bool completed
  +Question next_question
  +list~str~ activated_probes
}

class IntakeAnswerRequest {
  +UUID session_id
  +str question_code
  +Any value
}

class IntakeAnswerResponse {
  +IntakeSession session
  +dict~str, Any~ profile_patch
  +list~str~ missing_required_fields
}

class MaturityPrediction {
  +MaturityStage diagnosed_stage
  +MaturityStage declared_stage
  +GapLevel gap_level
  +float confidence
  +list~EvidenceItem~ evidence
  +list~str~ triggered_rules
  +str model_version
}

class SubScore {
  +str name
  +float value
  +float weight
  +float contribution
  +bool fundamental
}

class Score {
  +str name
  +float value
  +float confidence
  +list~SubScore~ sub_scores
  +list~str~ missing_criteria
  +list~str~ anomalies
  +str highest_leverage_action
  +list~str~ triggered_rules
  +str version
}

class CompositeScores {
  +list~Score~ scores
  +str version
  +by_name() dict~str, Score~
}

class Blocker {
  +str id
  +BlockerType type
  +Severity severity
  +float confidence
  +int priority
  +list~str~ evidence
  +bool is_missing_information
  +MaturityStage related_stage
}

class BlockerResult {
  +list~Blocker~ blockers
  +str model_version
}

class ConfidenceReport {
  +float overall_confidence
  +list~str~ missing_fields
  +list~str~ ambiguous_fields
  +bool manual_review_required
}

class ResourceMatch {
  +str resource_id
  +str name
  +str institution
  +CountryCode country
  +str type
  +float relevance_score
  +str source_url
  +list~str~ source_chunk_ids
  +list~str~ matched_reasons
  +list~MaturityStage~ eligible_stages
  +list~dict~ eligibility_conditions
  +bool synthetic
}

class EligibilityResult {
  +str resource_id
  +EligibilityStatus status
  +list~str~ matched_conditions
  +list~str~ failed_conditions
  +list~str~ missing_conditions
}

class RoadmapAction {
  +str id
  +str title
  +RoadmapHorizon horizon
  +int priority
  +str rationale
  +list~str~ addresses_blocker_ids
  +str addresses_score
  +list~str~ resource_ids
  +list~str~ depends_on
  +ActionStatus status
}

class Roadmap {
  +UUID roadmap_id
  +UUID project_id
  +list~RoadmapAction~ actions
}

class TenderProbeResult {
  +TenderReadinessStatus status
  +int score
  +list~str~ evidence
  +list~str~ missing_fields
}

class ProgressEvent {
  +UUID event_id
  +UUID project_id
  +str action_id
  +str event_type
  +datetime created_at
}

class AnalysisResult {
  +UUID project_id
  +ProjectProfile profile
  +MaturityPrediction maturity
  +CompositeScores scores
  +BlockerResult blockers
  +ConfidenceReport confidence
  +list~ResourceMatch~ resources
  +list~EligibilityResult~ eligibility
  +Roadmap roadmap
  +dict~str, str~ explanations
  +datetime generated_at
}

class DashboardResponse {
  +UUID project_id
  +ProjectProfile profile
  +AnalysisResult analysis
  +list~ProgressEvent~ progress_events
}

ContractModel <|-- ProjectCreateRequest
ContractModel <|-- ProjectProfile
ContractModel <|-- EvidenceItem
ContractModel <|-- Question
ContractModel <|-- IntakeSession
ContractModel <|-- IntakeAnswerRequest
ContractModel <|-- IntakeAnswerResponse
ContractModel <|-- MaturityPrediction
ContractModel <|-- SubScore
ContractModel <|-- Score
ContractModel <|-- CompositeScores
ContractModel <|-- Blocker
ContractModel <|-- BlockerResult
ContractModel <|-- ConfidenceReport
ContractModel <|-- ResourceMatch
ContractModel <|-- EligibilityResult
ContractModel <|-- RoadmapAction
ContractModel <|-- Roadmap
ContractModel <|-- TenderProbeResult
ContractModel <|-- ProgressEvent
ContractModel <|-- AnalysisResult
ContractModel <|-- DashboardResponse

ProjectProfile "1" o-- "0..*" EvidenceEntry : evidence_ledger
IntakeSession "1" o-- "0..1" Question : next_question
IntakeAnswerResponse "1" o-- "1" IntakeSession : session
MaturityPrediction "1" o-- "0..*" EvidenceItem : evidence
CompositeScores "1" o-- "1..*" Score : scores
Score "1" o-- "0..*" SubScore : sub_scores
BlockerResult "1" o-- "0..*" Blocker : blockers
Roadmap "1" o-- "0..*" RoadmapAction : actions
AnalysisResult "1" o-- "1" ProjectProfile : profile
AnalysisResult "1" o-- "1" MaturityPrediction : maturity
AnalysisResult "1" o-- "1" CompositeScores : scores
AnalysisResult "1" o-- "1" BlockerResult : blockers
AnalysisResult "1" o-- "1" ConfidenceReport : confidence
AnalysisResult "1" o-- "0..*" ResourceMatch : resources
AnalysisResult "1" o-- "0..*" EligibilityResult : eligibility
AnalysisResult "1" o-- "1" Roadmap : roadmap
DashboardResponse "1" o-- "1" ProjectProfile : profile
DashboardResponse "1" o-- "0..1" AnalysisResult : analysis
DashboardResponse "1" o-- "0..*" ProgressEvent : progress_events
RoadmapAction --> Blocker : addresses_blocker_ids
RoadmapAction --> ResourceMatch : resource_ids
EligibilityResult --> ResourceMatch : resource_id
ProgressEvent --> RoadmapAction : action_id
```

## 6. Enums metier essentiels

```mermaid
classDiagram
direction TB

class CountryCode {
  <<enumeration>>
  TN
  MA
  DZ
}

class BusinessType {
  <<enumeration>>
  traditional_business
  startup
}

class ActorType {
  <<enumeration>>
  entrepreneur
  startupper
}

class MaturityStage {
  <<enumeration>>
  IDEATION
  MARKET_VALIDATION
  STRUCTURATION
  FUNDRAISING
  LAUNCH_PLANNING
  GROWTH
}

class GapLevel {
  <<enumeration>>
  NONE
  LOW
  MEDIUM
  HIGH
}

class Severity {
  <<enumeration>>
  LOW
  MEDIUM
  HIGH
  CRITICAL
}

class BlockerType {
  <<enumeration>>
  MARKET_VALIDATION_BLOCKER
  LEGAL_BLOCKER
  FINANCIAL_BLOCKER
  TEAM_BLOCKER
  COMMERCIAL_BLOCKER
  TECHNICAL_BLOCKER
  SCALABILITY_BLOCKER
  GREEN_BLOCKER
  ADMINISTRATIVE_BLOCKER
  EXPORT_BLOCKER
  TENDER_READINESS_BLOCKER
}

class EligibilityStatus {
  <<enumeration>>
  ELIGIBLE
  POSSIBLY_ELIGIBLE
  NOT_ELIGIBLE
  INSUFFICIENT_DATA
}

class RoadmapHorizon {
  <<enumeration>>
  IMMEDIATE
  SHORT_TERM
  MEDIUM_TERM
}

class ActionStatus {
  <<enumeration>>
  TODO
  IN_PROGRESS
  DONE
}

class EvidenceStatus {
  <<enumeration>>
  CONFIRMED
  UNVERIFIED
  CONTRADICTED
  MISSING
}

class EvidenceStage {
  <<enumeration>>
  S1
  S2
  S3
  S4
  S5
  S6
}
```

## 7. Diagramme de classes: services domaine et orchestration locale

Source: `shared/domain/*`, `shared/model_interfaces/base.py`,
`shared/application/orientation_pipeline.py`.

```mermaid
classDiagram
direction LR

class MaturityPredictor {
  <<Protocol>>
  +predict(ProjectProfile) MaturityPrediction
}

class ScoreCalculator {
  <<Protocol>>
  +calculate(ProjectProfile) CompositeScores
}

class BlockerDetector {
  <<Protocol>>
  +detect(ProjectProfile, MaturityPrediction) BlockerResult
}

class DiagnosticProbe {
  <<Protocol>>
  +should_activate(ProjectProfile) bool
  +questions(ProjectProfile) list~Question~
  +evaluate(ProjectProfile) TenderProbeResult
}

class RuleBasedMaturityPredictor {
  +str name
  +str version
  +predict(ProjectProfile) MaturityPrediction
  -_gap_level(MaturityStage, MaturityStage) GapLevel
  -_confidence(ProjectProfile, MaturityStage) float
}

class LedgerMaturityPredictor {
  +str name
  +str version
  +predict(ledger, declared_stage, founding_date) MaturityPrediction
  -_gap_level(MaturityStage, MaturityStage) GapLevel
}

class SklearnMaturityPredictor {
  +RuleBasedMaturityPredictor fallback
  +load()
  +predict(ProjectProfile) MaturityPrediction
  +predict_model(BaseModel) BaseModel
}

class CriterionSpec {
  +str name
  +str field
  +float weight
  +bool fundamental
  +Any extractor
  +str rule_id
}

class AnomalyRule {
  +str anomaly_id
  +str description
  +list~str~ penalised_fields
  +Any check
}

class WeightedRuleScoreCalculator {
  +float lambda_penalty
  +calculate(ProjectProfile) CompositeScores
  +calculate_with_ledger(ProjectProfile, ledger) CompositeScores
  +compute(ProjectProfile) CompositeScores
  +weak_scores(CompositeScores, float) dict~str, Score~
  +green_band(float) str
}

class ModelBasedScoreCalculator {
  +WeightedRuleScoreCalculator fallback
  +load()
  +calculate(ProjectProfile) CompositeScores
  +predict(BaseModel) BaseModel
}

class RuleBasedBlockerDetector {
  +str name
  +str version
  +detect(ProjectProfile, MaturityPrediction) BlockerResult
}

class TenderReadinessProbe {
  +str code
  +should_activate(ProjectProfile) bool
  +questions(ProjectProfile) list~Question~
  +evaluate(ProjectProfile) TenderProbeResult
}

class DomainFunctions {
  <<module>>
  +assess_confidence(profile, maturity, scores, blockers) ConfidenceReport
  +match_resources(profile, maturity, scores, blockers, limit) list~ResourceMatch~
  +evaluate_eligibility(profile, resources) list~EligibilityResult~
  +build_roadmap(profile, blockers, scores, resources, eligibility) Roadmap
}

class InMemoryOrientationPipeline {
  +dict projects
  +dict sessions
  +dict analyses
  +dict progress_events
  +AdaptiveIntakeEngine intake
  +RuleBasedMaturityPredictor maturity
  +WeightedRuleScoreCalculator scoring
  +RuleBasedBlockerDetector blockers
  +create_project(ProjectCreateRequest) ProjectProfile
  +start_intake(UUID) IntakeSession
  +answer_intake(UUID, IntakeAnswerRequest) IntakeAnswerResponse
  +run_analysis(UUID) AnalysisResult
  +dashboard(UUID) DashboardResponse
  +complete_action(UUID, str) DashboardResponse
}

MaturityPredictor <|.. RuleBasedMaturityPredictor
MaturityPredictor <|.. SklearnMaturityPredictor
ScoreCalculator <|.. WeightedRuleScoreCalculator
ScoreCalculator <|.. ModelBasedScoreCalculator
BlockerDetector <|.. RuleBasedBlockerDetector
DiagnosticProbe <|.. TenderReadinessProbe
SklearnMaturityPredictor --> RuleBasedMaturityPredictor : fallback
ModelBasedScoreCalculator --> WeightedRuleScoreCalculator : fallback
WeightedRuleScoreCalculator --> CriterionSpec : uses
WeightedRuleScoreCalculator --> AnomalyRule : uses
RuleBasedBlockerDetector --> TenderReadinessProbe : evaluates
RuleBasedMaturityPredictor --> ProjectProfile
RuleBasedMaturityPredictor --> MaturityPrediction
WeightedRuleScoreCalculator --> ProjectProfile
WeightedRuleScoreCalculator --> CompositeScores
RuleBasedBlockerDetector --> BlockerResult
DomainFunctions --> ConfidenceReport
DomainFunctions --> ResourceMatch
DomainFunctions --> EligibilityResult
DomainFunctions --> Roadmap
InMemoryOrientationPipeline *-- RuleBasedMaturityPredictor
InMemoryOrientationPipeline *-- WeightedRuleScoreCalculator
InMemoryOrientationPipeline *-- RuleBasedBlockerDetector
InMemoryOrientationPipeline --> DomainFunctions : calls
InMemoryOrientationPipeline --> AnalysisResult : creates
```

## 8. Diagramme de classes: intake adaptatif

Source: `shared/intake/contracts.py`, `shared/intake/engine.py`,
`shared/intake/session_manager.py`, `shared/intake/profile_writer.py`,
`shared/intake/extractor.py`.

```mermaid
classDiagram
direction LR

class IntakeModel {
  <<Pydantic>>
  +ConfigDict model_config
}

class Condition {
  +str field
  +ConditionOp op
  +Any value
  +str on
}

class FieldSpec {
  +str name
  +str type
  +dict~str, str~ description
  +list~str~ options
}

class IntakeQuestion {
  +str id
  +IntakePhase phase
  +dict~str, str~ text
  +list~str~ targets
  +list~FieldSpec~ extract_fields
  +list~Condition~ preconditions
  +bool is_probe
  +bool captures_declared_stage
  +render(str) Question
}

class ProbeRule {
  +str id
  +ProbeKind kind
  +list~Condition~ trigger
  +str ask
  +list~str~ inject
  +list~str~ mark_inferred
  +list~str~ confirm_fields
  +bool fire_once
}

class ContradictionRule {
  +str id
  +list~Condition~ when
  +str contradicted_field
  +str clarification_probe
  +dict~str, str~ reason
}

class LedgerEntry {
  +str field
  +Any value
  +EvidenceStatus status
  +str source_answer_id
  +str note
  +datetime updated_at
  +confidence float
}

class AnswerRecord {
  +str answer_id
  +str question_id
  +str raw_answer
  +datetime created_at
}

class MissingItem {
  +str field
  +MissingKind kind
  +float value
  +bool gates_next_stage
  +str reason
}

class IntakeState {
  +UUID session_id
  +UUID project_id
  +str lang
  +IntakePhase phase
  +dict~str, Any~ profile
  +dict~str, LedgerEntry~ ledger
  +str declared_stage
  +str declared_stage_source
  +list~dict~ pml_transcript
  +list~str~ asked_question_ids
  +list~str~ pending_probes
  +list~str~ fired_probes
  +list~dict~ contradictions
  +list~AnswerRecord~ answers
  +str current_question_id
  +bool completed
}

class ExtractionResult {
  +dict~str, Any~ extracted
  +dict~str, EvidenceStatus~ evidence_status
  +dict~str, Any~ unprompted_signals
  +bool degraded
}

class SessionStartResponse {
  +UUID session_id
  +Question first_question
}

class AnswerResponse {
  +Question next_question
  +bool diagnostic_ready
  +list~str~ fired_probes
  +list~dict~ contradictions
}

class DiagnosisResponse {
  +UUID session_id
  +bool completed
  +EvidenceStage frontier_stage
  +str declared_stage
  +MaturityPrediction diagnosis
  +CompositeScores scores
  +dict~str, LedgerEntry~ ledger
}

class StateResponse {
  +IntakePhase phase
  +EvidenceStage frontier_stage
  +EvidenceStage next_stage
  +int gates_satisfied
  +int gates_total
  +float percent_to_next
  +str declared_stage
  +bool completed
}

class SessionStore {
  <<Protocol>>
  +get(UUID) IntakeState
  +save(IntakeState)
  +delete(UUID)
}

class InMemorySessionStore {
  +dict states
  +get(UUID) IntakeState
  +save(IntakeState)
  +delete(UUID)
}

class RedisSessionStore {
  +str url
  +int ttl_seconds
  +get(UUID) IntakeState
  +save(IntakeState)
  +delete(UUID)
}

class ProfileWriter {
  <<Protocol>>
  +persist(IntakeState, AnswerRecord)
}

class InMemoryProfileWriter {
  +list writes
  +persist(IntakeState, AnswerRecord)
}

class PostgresProfileWriter {
  +Any session_factory
  +persist(IntakeState, AnswerRecord)
}

class ExtractionLLM {
  <<Protocol>>
  +complete(prompt) str
}

class Extractor {
  +ExtractionLLM provider
  +int max_attempts
  +extract(IntakeQuestion, raw_answer, lang) ExtractionResult
}

class IntakeEngine {
  +Extractor extractor
  +SessionStore session_store
  +ProfileWriter profile_writer
  +start_session(UUID, str) IntakeState
  +get_state(UUID) IntakeState
  +resume(UUID) IntakeState
  +apply_pml(UUID, payload) IntakeState
  +process_answer(UUID, raw_answer, question_id) IntakeState
  -_write(IntakeState, AnswerRecord, ExtractionResult)
  -_advance(IntakeState)
}

IntakeModel <|-- Condition
IntakeModel <|-- FieldSpec
IntakeModel <|-- IntakeQuestion
IntakeModel <|-- ProbeRule
IntakeModel <|-- ContradictionRule
IntakeModel <|-- LedgerEntry
IntakeModel <|-- AnswerRecord
IntakeModel <|-- MissingItem
IntakeModel <|-- IntakeState
IntakeModel <|-- ExtractionResult
IntakeModel <|-- SessionStartResponse
IntakeModel <|-- AnswerResponse
IntakeModel <|-- DiagnosisResponse
IntakeModel <|-- StateResponse

IntakeQuestion "1" o-- "0..*" FieldSpec : extract_fields
IntakeQuestion "1" o-- "0..*" Condition : preconditions
ProbeRule "1" o-- "0..*" Condition : trigger
ContradictionRule "1" o-- "0..*" Condition : when
IntakeState "1" o-- "0..*" LedgerEntry : ledger
IntakeState "1" o-- "0..*" AnswerRecord : answers
DiagnosisResponse "1" o-- "1" MaturityPrediction : diagnosis
DiagnosisResponse "1" o-- "1" CompositeScores : scores
DiagnosisResponse "1" o-- "0..*" LedgerEntry : ledger

SessionStore <|.. InMemorySessionStore
SessionStore <|.. RedisSessionStore
ProfileWriter <|.. InMemoryProfileWriter
ProfileWriter <|.. PostgresProfileWriter
ExtractionLLM <|.. Extractor
IntakeEngine *-- Extractor
IntakeEngine o-- SessionStore
IntakeEngine o-- ProfileWriter
IntakeEngine --> IntakeState
IntakeEngine --> ExtractionResult
IntakeEngine --> MissingItem : compute_missing
```

## 9. Diagramme de classes: classification / PML

Source: `shared/application/startup_classifier.py`,
`shared/application/router.py`,
`services/classification_service/app/api/startup_classifier.py`.

```mermaid
classDiagram
direction LR

class LLMClassifier {
  +LLMClassifyFn classify_fn
  +str label
  +classify(free_text, options, context) int
}

class DecisionNode {
  +str node_id
  +str question
  +str explanation
  +list options
  +str phase_result
  +str phase
  +str dimension
  +bool allow_free_text
  +add_option(option_text, next_node) DecisionNode
  +to_dict() dict
  +evaluate(classifier, transcript)
  +evaluate_with_answers(answers, classifier, transcript)
}

class IndustryProfile {
  +str key
  +str name
  +str family
  +dict overrides
  +text(slot_id, fallback) str
}

class Persona {
  +str name
  +str industry_key
  +str description
  +dict answer_pattern
  +str expected_phase
}

class OptionPayload {
  +int index
  +str text
}

class TranscriptEntry {
  +str node_id
  +str question
  +str chosen_answer_text
}

class QuestionPayload {
  +str session_industry_key
  +str node_id
  +str phase
  +str dimension
  +str question
  +str explanation
  +bool allow_free_text
  +list~OptionPayload~ options
  +bool is_terminal
}

class ResultPayload {
  +str session_industry_key
  +str node_id
  +str phase
  +str result_text
  +list~TranscriptEntry~ transcript
  +bool is_terminal
}

class AnswerRequest {
  +str session_industry_key
  +str node_id
  +int selected_option_index
  +str free_text
  +list~TranscriptEntry~ transcript_so_far
}

class StartupContracts {
  <<Pydantic DTOs>>
  +StartupStartRequest
  +StartupAnswerRequest
  +StartupQuestionPayload
  +StartupResultPayload
}

IndustryProfile --> DecisionNode : build_industry_tree
DecisionNode "1" o-- "0..*" DecisionNode : option next_node
DecisionNode --> LLMClassifier : free_text routing
Persona --> DecisionNode : test traversal
QuestionPayload "1" o-- "0..*" OptionPayload : options
ResultPayload "1" o-- "0..*" TranscriptEntry : transcript
AnswerRequest "1" o-- "0..*" TranscriptEntry : transcript_so_far
StartupContracts --> QuestionPayload : mirrors
StartupContracts --> ResultPayload : mirrors
```

## 10. Diagramme de classes: roadmap generee

Source: `services/roadmap_service/app/schemas.py`,
`services/roadmap_service/app/generator.py`,
`services/roadmap_service/app/repository.py`.

```mermaid
classDiagram
direction LR

class RoadmapResourceInput {
  +str resource_id
  +str name
  +str institution
  +str category
  +str eligibility_status
  +str source_url
}

class RoadmapBlockerInput {
  +str type
  +str severity
  +int priority_rank
  +bool stage_blocking
  +str recommended_action_key
  +list~str~ evidence
}

class RoadmapGenerationInput {
  +UUID project_id
  +str country
  +str business_type
  +str sector
  +str primary_goal
  +str declared_stage
  +str diagnosed_stage
  +float maturity_confidence
  +dict~str, float~ scores
  +dict score_details
  +list~RoadmapBlockerInput~ blockers
  +list~RoadmapResourceInput~ resources
  +list~str~ missing_fields
}

class RoadmapSummary {
  +str current_focus
  +str next_stage_target
  +float confidence
}

class GeneratedRoadmapAction {
  +str id
  +str title
  +str description
  +str horizon
  +int priority
  +str status
  +str estimated_effort
  +list~str~ addresses_blockers
  +list~str~ improves_scores
  +list~str~ depends_on
  +list~str~ evidence
  +list~str~ resource_ids
  +str reason
  +list~str~ source_urls
}

class MissingInformationAction {
  +str field
  +str reason
}

class GeneratedRoadmap {
  +UUID roadmap_id
  +UUID project_id
  +datetime generated_at
  +str roadmap_version
  +RoadmapSummary summary
  +list~GeneratedRoadmapAction~ actions
  +list~MissingInformationAction~ missing_information_actions
}

class RoadmapStatusPatch {
  +str status
}

class RoadmapGenerator {
  <<module>>
  +load_templates() dict
  +generate_roadmap(RoadmapGenerationInput) GeneratedRoadmap
}

class InMemoryRoadmapRepository {
  +dict _by_project
  +save(GeneratedRoadmap) GeneratedRoadmap
  +get(UUID) GeneratedRoadmap
  +patch_action(UUID, str, str) GeneratedRoadmap
}

RoadmapGenerationInput "1" o-- "0..*" RoadmapBlockerInput : blockers
RoadmapGenerationInput "1" o-- "0..*" RoadmapResourceInput : resources
GeneratedRoadmap "1" o-- "1" RoadmapSummary : summary
GeneratedRoadmap "1" o-- "0..*" GeneratedRoadmapAction : actions
GeneratedRoadmap "1" o-- "0..*" MissingInformationAction : missing_information_actions
RoadmapGenerator --> RoadmapGenerationInput
RoadmapGenerator --> GeneratedRoadmap
InMemoryRoadmapRepository o-- GeneratedRoadmap : stores by project
RoadmapStatusPatch --> GeneratedRoadmapAction : updates status
```

## 11. Diagramme de classes: intelligence scoring avancee

Source: `shared/domain/scoring_intelligence.py`. Cette couche est plus riche
que le `AnalysisResult` MVP. Elle sert a decomposer les scores, simuler des
contre-factuels, recommander des actions et produire des explications.

```mermaid
classDiagram
direction LR

class IntelligenceReport {
  +MilestoneRoadmap roadmap
  +list~ResourceRecommendation~ resources
  +list~CounterfactualResult~ top_actions
  +list~ScoreExplanation~ explanations
  +list~BottleneckAnalysis~ bottlenecks
  +SWOTAnalysis swot
  +FounderArchetype archetype
  +list~ConfidenceSignal~ confidence_signals
  +ReadinessReport readiness_report
  +BoardSummary board_summary
  +float overall_readiness
  +str generated_by
}

class ReadinessReport {
  +float overall_readiness
  +float readiness_without_penalty
  +float confidence_adjusted_readiness
  +float bottleneck_cost
  +float weakest_link_floor
  +list~ReadinessContribution~ contributions
  +str formula_trace
}

class ReadinessContribution {
  +str dimension
  +float raw_score
  +float weight
  +float confidence
  +float effective_score
  +float weighted_contribution
}

class CounterfactualResult {
  +str action_id
  +str action_title
  +float effort
  +MutationSet mutation_set
  +list~ScoreDelta~ score_deltas
  +float overall_readiness_gain
  +float leverage
  +str sector
  +str stage
}

class MutationSet {
  +str action_id
  +dict~str, Any~ field_mutations
  +list~str~ evidence_confirmations
  +list~str~ strategy_trace
  +list~str~ assumptions
}

class ScoreDelta {
  +str score_name
  +float before
  +float after
  +float delta
  +float confidence_delta
}

class MilestoneRoadmap {
  +list~Milestone~ milestones
  +list~str~ critical_path
  +float overall_readiness_now
  +float overall_readiness_after_all
  +ReadinessReport readiness_report
  +list~SequencedStep~ sequence_narrative
}

class Milestone {
  +str id
  +str title
  +str description
  +str rationale
  +str horizon
  +str addresses_score
  +list~str~ addresses_criteria
  +list~str~ blocked_by
  +float effort
  +float overall_readiness_gain
  +MutationSet mutation_set
}

class ScoreExplanation {
  +str score_name
  +ScoreDecomposition decomposition
  +str bottleneck_explanation
  +str high_score_low_confidence_signal
  +list~str~ quick_wins
}

class ScoreDecomposition {
  +str score_name
  +float composite_value
  +float c_base
  +float lambda_penalty_cost
  +str weakest_fundamental_criterion
  +list~CriterionContribution~ criterion_contributions
  +list~str~ anomaly_penalties
  +float missing_evidence_cost
  +float confidence_value
}

class FounderArchetype {
  +str archetype_id
  +str label
  +float confidence
  +float evidence_quality
  +list~ArchetypeSignal~ triggering_signals
  +str strategic_recommendation
  +str co_founder_fit
  +str next_stage_gate
}

class ScoringIntelligenceService {
  +analyse_sync(profile, scores) IntelligenceReport
  -_build_explanations(scores, decompositions, bottlenecks)
}

class Engines {
  <<domain engines>>
  GraphWeightedReadinessEngine
  ContextualMutationEngine
  CounterfactualEngine
  SectorAwareActionGenerator
  RecommendationSearchEngine
  DimensionGraphEngine
  ContributionAnalyser
  ArchetypeEngine
  ResourceRetriever
}

IntelligenceReport "1" o-- "1" MilestoneRoadmap
IntelligenceReport "1" o-- "1" ReadinessReport
IntelligenceReport "1" o-- "0..*" CounterfactualResult
IntelligenceReport "1" o-- "0..*" ScoreExplanation
IntelligenceReport "1" o-- "0..*" BottleneckAnalysis
IntelligenceReport "1" o-- "1" FounderArchetype
ReadinessReport "1" o-- "0..*" ReadinessContribution
CounterfactualResult "1" o-- "1" MutationSet
CounterfactualResult "1" o-- "0..*" ScoreDelta
MilestoneRoadmap "1" o-- "0..*" Milestone
Milestone "1" o-- "1" MutationSet
ScoreExplanation "1" o-- "1" ScoreDecomposition
FounderArchetype "1" o-- "0..*" ArchetypeSignal
ScoringIntelligenceService --> Engines : orchestrates
ScoringIntelligenceService --> IntelligenceReport : produces
```

## 12. Diagramme de classes: securite et auth MVP

Source: `services/api_gateway/app/auth/*`, `shared/security/*`.

```mermaid
classDiagram
direction LR

class UserPublic {
  +UUID id
  +str email
  +str full_name
  +bool is_active
  +bool is_verified
  +bool two_factor_enabled
  +datetime created_at
  +datetime updated_at
}

class UserRecord {
  +str password_hash
  +str two_factor_secret
  +str pending_two_factor_secret
}

class AuthResponse {
  +str access_token
  +str token_type
  +int expires_in
  +str refresh_token
  +bool requires_2fa
  +str temporary_login_token
  +UserPublic user
}

class AuthService {
  +dict users_by_email
  +dict refresh_sessions
  +register(RegisterRequest) UserPublic
  +login(email, password) AuthResponse
  +create_session(UserRecord) AuthResponse
  +refresh(refresh_token) AuthResponse
  +logout(refresh_token)
  +get_current_user(access_token) UserPublic
  +change_password(user_id, current, new)
  +setup_2fa(user_id) tuple
  +confirm_2fa(user_id, code) UserPublic
  +verify_2fa_login(temp_token, code) AuthResponse
  +disable_2fa(user_id, code) UserPublic
}

class TokenPayload {
  +str sub
  +str type
  +int exp
  +str jti
  +dict extra
}

class TokenFunctions {
  <<module>>
  +create_token(subject, type, secret, expires, extra) str
  +decode_token(token, secret, expected_type) TokenPayload
}

class EncryptedPayload {
  +bool encrypted
  +str algorithm
  +str key_id
  +str nonce
  +str ciphertext
  +datetime created_at
}

class DataEncryptor {
  +str key_id
  +generate_key() str
  +encrypt_json(payload, aad) EncryptedPayload
  +decrypt_json(envelope, aad) Any
}

class DecryptionLease {
  +str lease_id
  +str subject_id
  +str purpose
  +datetime created_at
  +datetime expires_at
  +is_expired(now) bool
}

class DecryptionLeaseManager {
  +timedelta default_ttl
  +dict leases
  +create_lease(subject_id, purpose, ttl) DecryptionLease
  +validate(lease_id, subject_id, purpose) DecryptionLease
  +revoke(lease_id)
  +cleanup()
  +active_count() int
}

UserPublic <|-- UserRecord
AuthResponse "1" o-- "0..1" UserPublic : user
AuthService --> UserRecord : stores
AuthService --> AuthResponse : returns
AuthService --> TokenFunctions : creates/decodes
TokenFunctions --> TokenPayload
DataEncryptor --> EncryptedPayload
DecryptionLeaseManager "1" o-- "0..*" DecryptionLease : active leases
```

## 13. Diagramme ER: base de donnees et migration initiale

`shared/database/models.py` mappe actuellement les tables principales
(`users`, `projects`, `project_profile_versions`, `audit_events`, `resources`,
`resource_chunks`, `evaluation_runs`). La migration `0001_initial.py` cree aussi
plusieurs tables JSONB par domaine avec la meme forme: `id`, `project_id`,
`payload`, `created_at`, `updated_at`, `version`.

```mermaid
erDiagram
    USERS ||--o{ PROJECTS : owns
    PROJECTS ||--o{ PROJECT_PROFILE_VERSIONS : versions
    PROJECTS ||--o{ JSON_DECISION_TABLES : project_id
    PROJECTS ||--o{ AUDIT_EVENTS : logs
    RESOURCES ||--o{ RESOURCE_CHUNKS : chunks

    USERS {
        uuid id PK
        string display_name
        datetime created_at
        datetime updated_at
        int version
    }

    PROJECTS {
        uuid id PK
        uuid user_id FK
        string country
        string business_type
        string declared_stage
        jsonb profile
        bool is_deleted
        datetime created_at
        datetime updated_at
        int version
    }

    PROJECT_PROFILE_VERSIONS {
        uuid id PK
        uuid project_id FK
        jsonb profile
        datetime created_at
        datetime updated_at
        int version
    }

    JSON_DECISION_TABLES {
        uuid id PK
        uuid project_id FK
        jsonb payload
        datetime created_at
        datetime updated_at
        int version
    }

    RESOURCES {
        uuid id PK
        string country
        string name
        string institution
        string resource_type
        jsonb metadata_json
        bool synthetic
        datetime created_at
        datetime updated_at
        int version
    }

    RESOURCE_CHUNKS {
        text id PK
        uuid resource_id FK
        text content
        jsonb metadata_json
        vector embedding
        datetime created_at
        datetime updated_at
        int version
    }

    AUDIT_EVENTS {
        uuid id PK
        uuid project_id
        string service
        string event_type
        jsonb payload
        datetime created_at
        datetime updated_at
        int version
    }

    EVALUATION_RUNS {
        uuid id PK
        jsonb metrics
        numeric average_latency
        datetime created_at
        datetime updated_at
        int version
    }
```

Tables regroupees dans `JSON_DECISION_TABLES`:

- `intake_sessions`
- `questions`
- `answers`
- `diagnoses`
- `maturity_predictions`
- `score_runs`
- `score_components`
- `blockers`
- `eligibility_results`
- `roadmaps`
- `roadmap_actions`
- `progress_events`
- `model_versions`
- `rule_versions`
- `evaluation_runs`

## 14. Frontend: routes, pages, hooks et clients API

Source: `frontend/src/main.tsx`, `frontend/src/api/*`, `frontend/src/hooks/*`.

```mermaid
flowchart TD
    ROOT[ReactDOM root] --> I18N[I18nProvider]
    I18N --> QUERY[QueryClientProvider]
    QUERY --> AUTH[AuthProvider]
    AUTH --> ROUTER[RouterProvider]

    ROUTER --> PUBLIC[Public routes]
    ROUTER --> PROTECTED[ProtectedRoute]

    PUBLIC --> LOGIN[LoginPage]
    PUBLIC --> REGISTER[RegisterPage]
    PUBLIC --> VERIFY[Verify2FAPage]

    PROTECTED --> LAYOUT[AppLayout]
    LAYOUT --> NAV[Sidebar + header + StageRail]
    LAYOUT --> OUTLET[Outlet pages]

    OUTLET --> HOME[HomeDashboardPage /dashboard]
    OUTLET --> NEW[NewProjectPage /projects/new]
    OUTLET --> INTAKE[ProjectIntakeFlow /projects/:id/intake]
    OUTLET --> DASH[DashboardPage /projects/:id/dashboard]
    OUTLET --> SCORES[ScoresPage /projects/:id/scores]
    OUTLET --> ROAD[RoadmapPage /projects/:id/roadmap]
    OUTLET --> RES[ResourcesPage /projects/:id/resources]
    OUTLET --> INTEL[IntelligencePage /projects/:id/intelligence]
    OUTLET --> JOURNEY[JourneyPage /projects/:id/journey]
    OUTLET --> SEC[SecuritySettingsPage /settings/security]

    HOME --> HOOKS[React Query hooks]
    DASH --> HOOKS
    ROAD --> HOOKS
    RES --> HOOKS
    INTAKE --> ADAPTIVE[adaptiveClient + classification client]
    SEC --> AUTHAPI[auth API client]

    HOOKS --> PROJECTS_API[projects.ts]
    HOOKS --> ROADMAP_API[roadmap.ts]
    HOOKS --> RES_API[resources.ts]
    PROJECTS_API --> CLIENT[client.ts request/uploadFile]
    ROADMAP_API --> CLIENT
    RES_API --> CLIENT
    AUTHAPI --> CLIENT
    ADAPTIVE --> GW[API Gateway localhost:5050]
    CLIENT --> GW
```

## 15. Services et endpoints internes

```mermaid
flowchart TB
    GW[API Gateway :5050]

    GW -->|/intake/start / /intake/answer| INTAKE_LEG[Intake Service legacy :5051]
    GW -->|/api/v1/intake/sessions/*| INTAKE_ADAPT[Intake Service adaptive :5051]
    GW -->|/api/v1/classification/*| CLASSIF[Classification Service :5061]
    GW -->|/profiles/projects/*| PROFILE[Profile Service :5052]
    GW -->|/maturity/predict| MATURITY[Maturity Service :5053]
    GW -->|/scores/calculate| SCORING[Scoring Service :5054]
    GW -->|/blockers/detect| BLOCKER[Blocker Service :5055]
    GW -->|/confidence/assess| CONF[Confidence Service :5056]
    GW -->|/resources/match| RESOURCE[Resource Service :5057]
    GW -->|/eligibility/check| ELIG[Eligibility Service :5058]
    GW -->|/roadmaps/build + /api/v1/projects/:id/roadmap| ROADMAP[Roadmap Service :5059]
    GW -->|/progress/actions/:id/complete| PROGRESS[Progress Service :5060]
    GW -.->|/assistant| ASSIST[Assistant Service :5064]
    GW -.->|/explain| EXPLAIN[Explainability Service :5061 in docs]
    INGEST[Knowledge Ingestion Service :5062] --> RESOURCE
    EVAL[Evaluation Service :5063] --> ART[Evaluation artifacts]
```

## 16. Lecture rapide des responsabilites

```mermaid
flowchart LR
    Profile[ProjectProfile] --> Intake[Intake]
    Intake --> Evidence[Evidence ledger]
    Evidence --> LedgerMaturity[LedgerMaturityPredictor]
    Evidence --> LedgerScoring[calculate_with_ledger]
    Profile --> RuleMaturity[RuleBasedMaturityPredictor]
    Profile --> RuleScoring[WeightedRuleScoreCalculator]
    RuleMaturity --> MaturityPrediction
    LedgerMaturity --> MaturityPrediction
    RuleScoring --> CompositeScores
    LedgerScoring --> CompositeScores
    MaturityPrediction --> Blockers[RuleBasedBlockerDetector]
    CompositeScores --> Confidence[assess_confidence]
    Blockers --> Confidence
    MaturityPrediction --> Resources[match_resources]
    CompositeScores --> Resources
    Blockers --> Resources
    Resources --> Eligibility[evaluate_eligibility]
    Eligibility --> Roadmap[build_roadmap / generate_roadmap]
    Roadmap --> Progress[ProgressEvent]
```

## 17. Notes de conception

- Le gateway est le point d'entree public: auth, CORS, tokens, routes protegees
  et orchestration.
- Les contrats metier sont centralises dans `shared/contracts`; les services
  retournent principalement ces DTOs.
- Les decisions MVP restent deterministes: regles YAML, calculateurs Python,
  matching lexical local et donnees synthetiques.
- Le LLM n'est pas responsable des decisions: il sert a classifier du texte
  libre dans le PML ou a produire de futures explications narratives.
- Le `InMemoryOrientationPipeline` sert aux tests, demos et services encore
  legerement persistants; PostgreSQL/Alembic sont prets pour remplacer cette
  couche progressivement.
- Le nouveau moteur d'intake est evidence-ledger-driven: il collecte des
  preuves, signale les contradictions et laisse le diagnostic a
  `LedgerMaturityPredictor` + `WeightedRuleScoreCalculator`.
