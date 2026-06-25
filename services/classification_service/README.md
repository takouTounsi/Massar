# Classification Service

This service exposes the startup "perceived maturity" classifier as a standalone microservice.

- API: `POST /api/v1/startup/session/start` and `POST /api/v1/startup/session/answer` (see `app/api/startup_classifier.py`).
- Purpose: classify a founder's answers into a perceived startup phase (Perceived Maturity Level — FUNDRAISING).
| Step                  | Short Description                                                                                                          |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Ideation**          | Generating, refining, and assessing business ideas to identify a viable opportunity and value proposition.                 |
| **Market Validation** | Testing customer demand, market needs, and solution fit through research, interviews, and early experiments.               |
| **Structuration**     | Establishing the business model, legal structure, operations, team organization, and strategic foundations.                |
| **Fundraising**       | Securing financial resources from grants, investors, loans, or other funding sources to support growth.                    |
| **Launch Planning**   | Preparing the product or service for market entry through execution planning, marketing, sales, and operational readiness. |
| **Growth**            | Expanding the business by increasing customers, revenue, partnerships, market reach, and operational capacity.             |

- Integration: the classification result is considered a "perceived state" and is injected into the intake pipeline (the Intake Engine will receive this perceived state and perform downstream verification: checking whether claims are backed by evidence, running probes, and flagging inconsistencies).

How it fits in the system
- The classifier returns a small structured payload describing the perceived phase and transcript of answers.
- The Intake Engine should treat this as an *opinion* (perceived state) and apply business rules, probes, and model-based checks to confirm or refute claimed facts.

Local dev
- Run tests in the repo root. The classifier uses a deterministic demo classifier when `USE_DEMO_CLASSIFIER=1`.
