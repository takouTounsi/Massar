# ADR-002 Service Boundaries

Status: accepted

Services are split by decision responsibility: intake, profile, maturity, scoring, blockers, confidence, resources, eligibility, roadmap and progress.

Shared contracts and domain primitives live in `shared/`; service routes remain thin and do not contain business logic.
