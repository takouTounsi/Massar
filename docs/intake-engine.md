# Adaptive Intake Engine — Integration Plan

> Living design doc for the MASSAR Adaptive Intake Engine. One component of the
> larger orientation engine. This document tracks where the engine plugs into
> the existing scaffold and the contracts it owns.

## Scope

The engine drives the loop:

```
user answer → profile update → missing-info detection
            → next-question selection → optional specialized probe
```

It **owns**: the dynamic questionnaire, evidence extraction from free AR/FR
text, the `evidence_ledger`, probe firing, and next-question selection.

It **does not**: assign a maturity stage, compute any score, or let the LLM make
any verdict. Those are downstream consumers (`shared/domain/maturity.py`,
`shared/domain/scoring.py`) that read the shared profile + `evidence_ledger`.

## Where it lives

New self-contained package `shared/intake/`, matching the existing convention
that cross-service logic lives under `shared/` (e.g. `shared/domain/`,
`shared/llm/`) and services stay thin (`services/<svc>/app/main.py`).

```
shared/intake/
  contracts.py            # pydantic contracts: ledger, state, extraction, questions, probes
  requirements.py         # SHARED requirements registry (data): field -> {stage_gates, scoring_criteria, fundamental}
  question_bank.py        # declarative questions + probes (FR/AR)
  session_manager.py      # Redis session CRUD + lifecycle (+ in-memory fallback)
  extractor.py            # THE ONLY LLM CALL in this engine (scoped schema)
  profile_writer.py       # Postgres profile + evidence_ledger writes (+ in-memory)
  contradiction_detector.py
  probe_engine.py         # declarative probe trigger rules
  missing_info.py         # required-evidence computation (frontier-relative)
  question_selector.py    # branching + information-value ranking + phases
  engine.py               # thin orchestrator: process_answer()
```

Service surface added to `services/intake_service/app/main.py` (new `/sessions/*`
routes), leaving the legacy `/intake/*` routes untouched.

## Reuse vs create

| Concern | Decision |
| --- | --- |
| `ProjectProfile`, `Question` | **Reuse** `shared/contracts/schemas.py`. The engine's `IntakeState.profile` is a plain dict that round-trips into `ProjectProfile`. |
| LLM client | **Reuse** `shared/llm` (`LLMProvider`, `MockLLMProvider`). The extractor wraps a provider; it is the only LLM call here. |
| Config / FastAPI / logging | **Reuse** `shared/config`, `shared/application/fastapi.create_service_app`. |
| DB session | **Reuse** `shared/database/session.get_session_factory` and the existing `intake_sessions` / `answers` / `project_profile_versions` JSONB tables (no new migration needed). |
| Evidence ledger / status | **Create** `EvidenceStatus` enum (shared) + `LedgerEntry` contract. New shared contract. |
| Stage taxonomy | **Create** `EvidenceStage` (S1–S6 document-gated). Crosswalk to the existing `MaturityStage` documented below. The engine never decides the stage. |
| Requirements registry | **Create** `shared/intake/requirements.py` — pure data, importable by maturity/scoring without importing the classifier/scorer. |
| Redis | **Create** `RedisSessionStore` (+ `InMemorySessionStore` fallback). Adds `redis` dep, `redis_url` setting, compose service. |

## Hard invariants (enforced)

1. LLM only extracts structured fields. Question selection is fully
   deterministic (`question_selector`, `missing_info`). No stage, no score.
2. Extractor is called with a schema **scoped to the current question's fields**
   only (`IntakeQuestion.extract_fields`), so it cannot invent fields.
3. `evidence_ledger` status per field is the shared contract:
   `CONFIRMED | UNVERIFIED | CONTRADICTED | MISSING`.
4. Missing-info is **frontier-relative** — only ask what could change the next
   stage gate or fill a fundamental scoring field.
5. Shared requirements registry maps each evidence field →
   `{stage_gates, scoring_criteria, fundamental}` as data.
6. `declared_stage` is captured once, stored isolated, never feeds extraction or
   selection.

## EvidenceStage (S1–S6) ↔ MaturityStage crosswalk

The document-evidence-gated taxonomy is the canonical gating taxonomy for the
registry. The downstream rule classifier keeps using `MaturityStage`; the
crosswalk lets it read the same gates if desired.

| S | Meaning (artifact-gated) | MaturityStage |
| --- | --- | --- |
| S1 | idea-only | IDEATION |
| S2 | problem validated / informal | MARKET_VALIDATION |
| S3 | prototype + entity started (RNE) | STRUCTURATION |
| S4 | real commercial traction (factures w/ TVA, SARL/SUARL) | FUNDRAISING |
| S5 | proven model + fiscal compliance (CNSS, TVA filings) | LAUNCH_PLANNING |
| S6 | investment-ready / scaling | GROWTH |

Stages gate on real artifacts (RNE, TVA, CNSS, factures), not declared intent.
The intake engine encodes *which evidence field* each gate needs; it never
assigns the stage.

## Turn loop — `engine.process_answer(state, raw_answer, question_id)`

1. **EXTRACT** — `extractor` (scoped schema) → `{extracted, evidence_status,
   unprompted_signals}`. Unprompted signals are written `UNVERIFIED` so we never
   re-ask volunteered info.
2. **UPDATE** — `contradiction_detector` reconciles against the existing profile
   using Tunisian regulatory-coherence rules; `profile_writer` persists fields +
   ledger + `source_answer_id` + timestamp. `founding_date` stored early.
3. **PROBES** — `probe_engine` evaluates triggers (EVIDENCE / SECTOR /
   STAGE_SKIP), `fire_once`, pushes onto `pending_probes`.
4. **MISSING-INFO** — dry-evaluate stage gates from the registry (no classifier
   import). MISSING → askable; UNVERIFIED → evidence probe; STRUCTURAL_GAP
   (present-but-negative) → blocker, surfaced not asked.
5. **SELECT** — pending probes first, else highest info-value askable question
   respecting preconditions and the 4-phase progressive disclosure, else
   TERMINATE (`diagnostic_ready`).

## API surface (`services/intake_service`)

```
POST /sessions                -> {session_id, first_question}
POST /sessions/{id}/answers   -> {next_question} | {diagnostic_ready: true}
GET  /sessions/{id}/state     -> {phase, percent_complete, declared_stage}
POST /sessions/{id}/resume    -> rehydrate, re-run missing-info, continue
```

## Conflicts / ambiguities found

- **Existing `AdaptiveIntakeEngine`** (`shared/domain/intake.py`) is a thin
  placeholder, wired into `services/intake_service` and
  `shared/application/orientation_pipeline.py` (used by the api_gateway +
  `tests/integration/test_gateway_flow.py`). Treated as a **soft conflict**: it
  is left intact on the legacy `/intake/*` routes; the new engine is additive on
  `/sessions/*`. No overwrite.
- **Taxonomy mismatch**: existing `MaturityStage` is generic; the registry uses
  `EvidenceStage` S1–S6. Resolved via the crosswalk above.
- **Redis** was not present in the scaffold — added with an in-memory fallback so
  the engine and its tests are deterministic without a running Redis.

## Build order (commit at each step)

1. Data contracts: profile fields + evidence_ledger + requirements registry.
2. question_bank (FR/AR) + session_manager: static linear walk persists/resumes.
3. extractor against scoped-schema contract (LLM mocked in tests).
4. probe_engine (evidence + sector first, stage_skip last).
5. missing_info + question_selector → adaptive.
6. contradiction_detector + resume.

## Extraction hardening (the single LLM call)

- Scoped JSON schema per question; tolerant parsing (strips ``` fences / prose,
  falls back to the first balanced `{...}`); retries (`max_attempts`), then a
  `degraded` flag the engine logs for observability.
- `json_mode` hint flows to the provider (`response_format=json_object`).
- PII (emails, phone numbers, long IDs) is redacted from the *stored* answer;
  the extractor still sees the original.
- `shared/intake/extraction_eval.py` + `data/intake/extraction_eval.json` give a
  field-level precision/recall + status-accuracy harness to measure prompt /
  provider changes (mock ≈ 0; point at a real provider for signal).

## Downstream handoff (consumers read the ledger)

The registry now exposes ledger-driven gate logic so the classifier/scorer read
the **same** evidence contract the engine writes, without importing the engine:

- `requirements.frontier_stage / gate_satisfied / contradicted_gates` — single
  source of truth (the engine's `missing_info.frontier_stage` delegates here).
- `requirements.EVIDENCE_TO_MATURITY` — S1–S6 → `MaturityStage` crosswalk.
- `requirements.evidence_justification` (ej) / `criteria_evidence_factor` — the
  scorer's CONFIRMED→ej=1 / UNVERIFIED→ej=0 bridge.
- `domain.maturity.LedgerMaturityPredictor` — diagnoses a stage from the ledger
  (CONFIRMED advances the frontier, UNVERIFIED/MISSING degrade confidence,
  CONTRADICTED + confirmed-but-insufficient gates are surfaced as blockers,
  `founding_date` drives a young-company over-claim signal).
- `domain.scoring.WeightedRuleScoreCalculator.calculate_with_ledger` — same
  headline scores, confidence scaled by evidence justification.

The intake engine still never assigns a stage or a score; it only produces the
ledger these consumers read.

## Deferred (explicitly not built)

Calibrated ML classifier, IRT/CAT item selection, cross-encoder reranker.
Rules + info-value heuristic only.
