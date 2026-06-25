# Data Model

Alembic migration `0001_initial` creates the tables requested for the MVP:

- users, projects, project_profile_versions
- intake_sessions, questions, answers
- diagnoses, maturity_predictions
- score_runs, score_components
- blockers
- resources, resource_chunks
- eligibility_results
- roadmaps, roadmap_actions
- progress_events, audit_events
- model_versions, rule_versions, evaluation_runs

Flexible evidence and decision payloads use JSONB. `resource_chunks.embedding` uses `vector(32)` with an ivfflat cosine index.
