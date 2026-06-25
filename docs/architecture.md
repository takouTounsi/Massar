# Architecture

The MVP is a service-oriented monorepo. Each service exposes `/health` and `/ready`, owns a narrow responsibility and shares Pydantic contracts from `shared/contracts`.

Communication is HTTP in Docker Compose. Tests and scripts use a local orchestrator mode backed by the same domain services, which keeps the demo deterministic.

```mermaid
flowchart LR
    UI[Frontend] --> GW[API Gateway]
    GW --> INTAKE[Adaptive Intake]
    INTAKE --> PROFILE[Profile Service]
    PROFILE --> MAT[Maturity Service]
    PROFILE --> SCORE[Scoring Service]
    PROFILE --> BLOCK[Blocker Service]
    MAT --> CONF[Confidence Service]
    SCORE --> CONF
    BLOCK --> CONF
    CONF --> EXPLAIN[Explainability Service]
    MAT --> RESOURCE[Resource Matcher]
    SCORE --> RESOURCE
    BLOCK --> RESOURCE
    RESOURCE --> ELIG[Eligibility Checker]
    ELIG --> ROADMAP[Roadmap Service]
    ROADMAP --> PROGRESS[Progress Service]
    PROGRESS --> PROFILE
```

Future migration points are explicit: HTTP orchestration can be replaced by a broker, in-memory repositories by SQLAlchemy repositories, and rule-based predictors by versioned model providers.
