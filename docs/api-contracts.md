# API Contracts

Public gateway endpoints:

- `GET /health`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/intake/start`
- `POST /api/v1/projects/{project_id}/intake/answer`
- `POST /api/v1/projects/{project_id}/analysis/run`
- `GET /api/v1/projects/{project_id}/dashboard`
- `GET /api/v1/projects/{project_id}/roadmap`
- `POST /api/v1/projects/{project_id}/progress`
- `POST /api/v1/projects/{project_id}/assistant`

Internal services expose typed endpoints for maturity prediction, scoring, blocker detection, confidence assessment, resource matching, eligibility checks and roadmap building.

Swagger is available at `http://localhost:5050/docs` when the gateway is running.
