# Massar
## Evaluation Report
### Metrics, Test Protocol, Results and Limitations

Generated on 2026-06-25 from local repository artifacts.

## 1. Executive Summary

Massar is evaluated as a deterministic, evidence-aware entrepreneurial orientation system. The current MVP does not predict long-term startup success; it evaluates stage readiness, maturity diagnosis, score consistency, blockers, evidence confidence, anomaly detection, roadmap grounding, resource matching, eligibility, security behavior, and robustness under incomplete or contradictory inputs.

The evaluation uses the current executable code, synthetic fixtures, local JSON resources, unit/integration tests, and generated artifacts. No PowerPoint, PDF, DOCX, or pitch deck file was found in the repository workspace during inspection, so product context came from `README.md`, `ARCHITECTURE.md`, and Markdown documents under `docs/`.

| Area | Measured result | Source |
| --- | --- | --- |
| Maturity diagnosis | Accuracy 49.0%; Macro F1 0.407 | `artifacts/evaluation/results.json` |
| Blocker detection | Micro F1 0.817; Macro F1 0.758 | `scripts/run_evaluation.py` |
| Scoring reproducibility | 100.0% | `shared/domain/scoring.py` |
| Lambda penalty correctness | 100.0% | `artifacts/evaluation/metrics.json` |
| Anomaly rules | Accuracy 100.0%; false-alert rate 0.0% | `artifacts/evaluation/test_case_inventory.json` |
| MVP resource matching | Precision@3 0.583; Recall@3 0.625; MRR 0.750 | `data/evaluation/evaluation_cases.json` |
| Roadmap grounding | 100.0% | `shared/domain/roadmap.py` |
| Robustness | No-crash rate 100.0% | `scripts/run_evaluation.py` |
| Security encryption check | Pass | `tests/unit/test_security.py` |

## 2. Evaluation Scope

The evaluation covers the implemented MVP paths that can run locally without external services:

- deterministic scoring and weighted readiness rules;
- rule-based maturity diagnosis;
- blocker and anomaly detection;
- evidence and confidence behavior;
- rule-based resource matching over the current local JSON corpus;
- eligibility checks when metadata is available;
- roadmap action grounding and dependency checks;
- protected API route behavior for unauthenticated access;
- AES-GCM encryption and temporary decryption lease behavior;
- local in-process latency for scoring, resource matching, and full in-memory analysis.

Out of scope for measured results: real entrepreneur outcomes, expert-labelled production data, production Docker latency, pgvector retrieval, SHAP explanations, and stable counterfactual action impact metrics. These are reported as not measured where applicable.

## 3. System Components Evaluated

| Component type | Implementation inspected | Evaluation approach |
| --- | --- | --- |
| Scoring engine | `shared/domain/scoring.py`, `services/scoring_service` | Formula consistency, reproducibility, penalty behavior, score hints |
| Maturity diagnosis | `shared/domain/maturity.py`, `services/maturity_service` | Agreement with labelled synthetic maturity stages |
| Blocker engine | `shared/domain/blockers.py`, `services/blocker_service` | Precision, recall, F1 on synthetic blocker labels |
| Anomaly engine | `shared/domain/scoring.py` | Rule correctness and clean-case false-alert check |
| Confidence | `shared/domain/confidence.py`, evidence ledger hooks | Missing-data visibility and confidence scaling |
| Resource matching | `shared/domain/resources.py`, `data/knowledge_base/resources.json` | Precision@3, Recall@3, MRR, grounding |
| Eligibility | `shared/domain/eligibility.py` | Rule status agreement where expected labels exist |
| Roadmap | `shared/domain/roadmap.py`, `services/roadmap_service` | Grounding, resource validity, dependency compliance |
| Security | `shared/security`, `services/api_gateway/app/auth` | Encryption round-trip, plaintext absence, lease expiry, protected route |
| LLM layer | `shared/llm` | Fallback behavior only; not used for score correctness |

The current executable score names are `Market Score`, `Operational Score`, `Scalability Score`, `Innovation Score`, and `Green Score`. The report also notes one alignment risk: some frontend/demo documentation references `commercial_offer_score`, while the measured scoring engine emits `Operational Score`.

## 4. Evaluation Dataset and Test Cases

The dataset is explicitly marked as synthetic and is suitable for hackathon validation of deterministic behavior, not for real-world performance claims.

| Dataset item | Count | Source |
| --- | --- | --- |
| Synthetic entrepreneur profiles | 100 | `data/synthetic/entrepreneur_profiles.csv` |
| Blocker labels | 100 | `data/synthetic/blocker_labels.csv` |
| Scoring hints | 100 | `data/synthetic/scoring_cases.csv` |
| Resource query scenarios | 5 | `data/evaluation/evaluation_cases.json` |
| Roadmap profiles evaluated | 25 | `scripts/run_evaluation.py` |
| Robustness cases | 5 | `artifacts/evaluation/test_case_inventory.json` |

`synthetic_evaluation_dataset`: `true`.

## 5. Test Protocol

The evaluation was run with deterministic local Python scripts. The protocol was:

1. Load synthetic profiles, scoring hints, blocker labels, and resource query fixtures.
2. Convert profile rows into `ProjectProfile` contracts.
3. Run maturity, scoring, blocker, resource, eligibility, roadmap, robustness, and security checks using repository code.
4. Write machine-readable artifacts to `artifacts/evaluation/`.
5. Run a local in-process latency benchmark without LLM calls.
6. Generate this Markdown and PDF report from the artifacts.

Commands used:

```powershell
python scripts\run_evaluation.py
python scripts\run_performance_benchmark.py
python scripts\generate_evaluation_report_data.py
python -m pytest -q
```

## 6. Metrics

Metric definitions used in the generated artifacts:

| Metric | Definition |
| --- | --- |
| Maturity accuracy | Correct diagnosed maturity labels divided by evaluated profiles. |
| Macro F1 | Unweighted mean of per-stage F1 scores. |
| High-risk false-ready rate | Projects classified as Funding/Growth ready when expected labels indicate missing readiness evidence. |
| Blocker precision/recall/F1 | Multi-label blocker agreement against synthetic labels. |
| Score MAE | Mean absolute error between deterministic score output and synthetic score hints. |
| Reproducibility rate | Repeated deterministic scoring outputs that are identical. |
| Lambda penalty correctness | Expected weakest-link penalty cases correctly penalized. |
| Anomaly detection accuracy | Expected anomaly IDs detected in targeted scenarios. |
| False-alert rate | Clean anomaly scenario producing unexpected anomaly output. |
| Precision@3 | Relevant returned resources in top three divided by three. |
| Recall@3 | Relevant returned resources in top three divided by expected relevant resources. |
| MRR | Mean reciprocal rank of the first relevant resource. |
| Source grounding rate | Returned resources that reference a known local resource source. |
| Roadmap grounding rate | Actions linked to a blocker, weak score, maturity gap, or resource. |
| No-crash rate | Robustness scenarios completed without unhandled failure. |

## 7. Results

### 7.1 Maturity Diagnosis
| Metric | Value |
| --- | --- |
| Accuracy | 49.0% |
| Macro F1 | 0.407 |
| High-risk false-ready rate | 17.0% |
| High-risk false-ready count | 17 |

Per-stage results:
| Stage | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| IDEATION | 1.000 | 1.000 | 1.000 | 17 |
| MARKET_VALIDATION | 0.529 | 0.529 | 0.529 | 17 |
| STRUCTURATION | 0.000 | 0.000 | 0.000 | 17 |
| FUNDRAISING | 0.467 | 0.412 | 0.437 | 17 |
| LAUNCH_PLANNING | 0.000 | 0.000 | 0.000 | 16 |
| GROWTH | 0.314 | 1.000 | 0.478 | 16 |

### 7.2 Scoring Engine
| Metric | Value |
| --- | --- |
| Profiles scored | 100 |
| Score output count rate | 100.0% |
| Score name set | Green Score, Innovation Score, Market Score, Operational Score, Scalability Score |
| Market Score MAE against synthetic hint | 25.025 |
| Scalability Score MAE against synthetic hint | 11.083 |
| Reproducibility rate | 100.0% |
| Lambda penalty correctness | 100.0% |
| Confidence ledger scaling | Pass |

### 7.3 Blockers and Anomalies
| Blocker | TP | FP | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| MARKET_VALIDATION_BLOCKER | 34 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| TENDER_READINESS_BLOCKER | 8 | 1 | 0 | 0.889 | 1.000 | 0.941 |
| SCALABILITY_BLOCKER | 5 | 20 | 0 | 0.200 | 1.000 | 0.333 |

Overall blocker Micro F1: 0.817. Overall blocker Macro F1: 0.758.

Anomaly scenario results:
| Test scenario | Expected anomaly | Actual output | Pass/Fail | Notes |
| --- | --- | --- | --- | --- |
| high_traction_no_documented_evidence | high_traction_no_documented_evidence | high_traction_no_documented_evidence | Pass | Targeted rule scenario |
| manual_processes_limit_growth | manual_processes_limit_growth | high_traction_no_documented_evidence, manual_processes_limit_growth | Pass | Targeted rule scenario |
| high_innovation_claim_no_ip | high_innovation_claim_no_ip | high_innovation_claim_no_ip | Pass | Targeted rule scenario |
| revenue_without_mvp_artifact | revenue_without_mvp_artifact | revenue_without_mvp_artifact | Pass | Targeted rule scenario |
| high_sdg_without_practices | high_sdg_without_practices | high_sdg_without_practices | Pass | Targeted rule scenario |
Clean-case false-alert rate: 0.0%.

### 7.4 Roadmap
| Metric | Value |
| --- | --- |
| Profiles evaluated | 25 |
| Generated actions | 84 |
| Roadmap grounding rate | 100.0% |
| Resource reference validity rate | 100.0% |
| Dependency compliance rate | 100.0% |
| Counterfactual consistency rate | Not measured |

Counterfactual evaluation status: Not measured in current MVP. Reason: CounterfactualEngine exists in shared/domain/scoring_intelligence.py but is not covered by a stable service endpoint or test fixture in the current runnable MVP.

## 8. Robustness and Edge-Case Tests

| Edge case | Expected behavior | Actual behavior | Pass/Fail |
| --- | --- | --- | --- |
| missing_fields_profile | No crash; missing fields visible | missing=['monthly_revenue', 'market_size_known', 'competition_understanding', 'revenue_model_clarity', 'process_automation_level', 'customer_retention'] | Pass |
| invalid_score_range_validation | Pydantic rejects invalid score range | ValidationError | Pass |
| llm_mock_fallback | Mock provider returns deterministic text | Diagnostic summary: stage=IDEATION; blockers=0; prompt=Explain | Pass |
| expired_decryption_lease | Expired lease is denied | LeaseExpired | Pass |
| unauthorized_project_route | Protected route returns 401/403 | 401 | Pass |

No-crash rate: 100.0%. Graceful degradation rate: 100.0%. Fallback success rate: 100.0%.

## 9. RAG and Resource Matching Evaluation

The current runnable MVP uses rule-based metadata/lexical resource matching over `data/knowledge_base/resources.json`. It is not a full vector RAG benchmark because no active vector retrieval or reranker endpoint was executed by the evaluation script.

| Metric | Value |
| --- | --- |
| Measured query count | 4 |
| Precision@3 | 0.583 |
| Recall@3 | 0.625 |
| MRR | 0.750 |
| Source grounding rate | 100.0% |
| Eligibility rule accuracy | 80.0% |

Resource query results:
| Case | Measured | Expected IDs | Returned IDs | P@3 | R@3 | MRR | Not measured reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rq_001_market_validation_funding | true | res-guide-001, res-guide-002, res-guide-004 | res-guide-001, res-guide-002, res-guide-004 | 1.000 | 1.000 | 1.000 |  |
| rq_002_export_quality | true | res-guide-003, res-guide-007 | res-guide-007, res-guide-005, res-guide-001 | 0.333 | 0.500 | 1.000 |  |
| rq_003_public_procurement_gap | false |  | res-guide-003, res-guide-006, res-guide-007 | Not measured | Not measured | Not measured | The current local resource corpus does not contain a public-procurement-specific resource. |
| rq_004_legal_formalization | true | res-guide-001, res-guide-002, res-guide-004 | res-guide-001, res-guide-002, res-guide-004 | 1.000 | 1.000 | 1.000 |  |
| rq_005_funding_evidence_pack | true | res-guide-001, res-guide-002, res-guide-004 | res-guide-005, res-guide-007, res-guide-003 | 0.000 | 0.000 | 0.000 |  |

## 10. Performance and Latency Evaluation

Benchmark note: Local in-process benchmark. This is not a Docker/PostgreSQL/pgvector production benchmark.

| Operation | Environment | Runs | p50 ms | p95 ms | Error rate | LLM enabled | Data source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Score calculation | local in-process Python on developer workstation | 30 | 0.103 | 0.205 | 0.0% | false | local CSV/JSON and in-memory services |
| Resource matching | local in-process Python on developer workstation | 30 | 0.481 | 0.934 | 0.0% | false | local CSV/JSON and in-memory services |
| Full in-memory analysis | local in-process Python on developer workstation | 20 | 1.537 | 2.786 | 0.0% | false | local CSV/JSON and in-memory services |

Production latency:
- **Production Latency**
  Status: Not measured in current MVP
  Reason: Only local in-process benchmarks are generated; Docker/PostgreSQL/pgvector production-scale benchmarks are not run by this script.
  Recommended next step: Run the benchmark through Docker Compose with warm services and persisted logs.

## 11. Explainability Evaluation

The MVP exposes explainability through deterministic score decomposition, blocker reasons, missing-data visibility, resource source references, and roadmap rationales. The measured explainability checks are structural and grounding-oriented rather than SHAP-based.

| Explainability area | Measured result | Evidence |
| --- | --- | --- |
| Score traceability | Implemented structurally through score breakdown fields | `shared/domain/scoring.py` |
| Diagnostic justification coverage | Covered indirectly by maturity/blocker outputs and missing-field checks | `shared/domain/maturity.py`, `shared/domain/confidence.py` |
| Source grounding | 100.0% | `artifacts/evaluation/results.json` |
| Roadmap coherence | 100.0% | `artifacts/evaluation/results.json` |
| Confidence visibility | Pass | `scripts/run_evaluation.py` |
| SHAP availability | Not measured | `docs/ml-strategy.md`, `shared/domain/maturity.py` |

SHAP is documented as a planned explainability mechanism for ML-backed services. It was not evaluated in the current rule-based MVP because no trained ML model was executed.

- **Shap Availability Rate**
  Status: Not measured in current MVP
  Reason: No executable SHAP or TreeExplainer integration is present; SklearnMaturityPredictor delegates to rule-based prediction.
  Recommended next step: Train/load a RandomForestClassifier and add a SHAP evaluation harness over a labelled validation set.

## 12. Limitations

The following limitations are supported by the current repository state and generated artifacts:

- The evaluation dataset is synthetic; there are no expert-labelled real entrepreneur profiles yet.
- Maturity and scoring behavior are currently deterministic/rule-based for the measured MVP paths.
- The local resource corpus is small, and one public-procurement test scenario was not measurable because no matching corpus item exists.
- The executable resource matching evaluation is MVP rule-based matching, not vector RAG.
- Production-scale latency through Docker Compose, PostgreSQL, and pgvector was not measured.
- SHAP and trained ML model explanations are documented/planned but were not executed.
- The counterfactual engine exists in `shared/domain/scoring_intelligence.py`, but its action-impact evaluation is not exposed through a stable measured service endpoint.
- Authentication, encryption, and decryption leases are MVP-level checks, not a production KMS/Vault deployment.
- Some demo/documentation naming still references `commercial_offer_score`, while the measured scoring engine emits `Operational Score`.

Additional not-measured items:
- **Rag Vector Metrics**
  Status: Not measured in current MVP
  Reason: The runnable resource service uses metadata/lexical rule matching over local JSON; no vector retrieval or reranker endpoint is active.
  Recommended next step: Expose a vector retrieval service and add query-level relevance labels for Precision@K, Recall@K, MRR, and source grounding.
- **Counterfactual Action Impact**
  Status: Not measured in current MVP
  Reason: CounterfactualEngine exists in shared/domain/scoring_intelligence.py but is not covered by a stable service endpoint or test fixture in the current runnable MVP.
  Recommended next step: Add stable fixtures for shared.domain.scoring_intelligence.MassarIntelligenceEngine and export counterfactual deltas.

## 13. Reproducibility Instructions

From the repository root:

```powershell
python -m pytest -q
python scripts\run_evaluation.py
python scripts\run_performance_benchmark.py
python scripts\generate_evaluation_report_data.py
```

Generated artifacts:

- `artifacts/evaluation/results.json`
- `artifacts/evaluation/metrics.json`
- `artifacts/evaluation/confusion_matrix.csv`
- `artifacts/evaluation/test_case_inventory.json`
- `artifacts/evaluation/latency_results.json`
- `docs/evaluation_report.md`
- `docs/evaluation_report.pdf`

No plots were generated because the report generator intentionally uses only the standard library and does not fabricate chart images.

## 14. Conclusion

The current Massar MVP has a reproducible evaluation harness for its deterministic orientation pipeline. It demonstrates measurable behavior for maturity diagnosis, scoring reproducibility, blocker detection, anomaly rules, MVP resource matching, roadmap grounding, robustness, authentication protection, and encryption lease behavior.

The strongest measured areas are deterministic reproducibility, lambda penalty correctness, targeted anomaly rule detection, roadmap grounding, robustness, and encryption checks. The weakest measured areas are maturity macro F1 and resource matching consistency on the small synthetic corpus. The main next step is to add expert-labelled real cases, a larger resource corpus, production benchmarks, stable counterfactual fixtures, and executable ML/RAG explainability evaluation.

## Appendix A — Test Case Inventory

Maturity profile IDs evaluated: 100. First ten: synthetic-profile-001, synthetic-profile-002, synthetic-profile-003, synthetic-profile-004, synthetic-profile-005, synthetic-profile-006, synthetic-profile-007, synthetic-profile-008, synthetic-profile-009, synthetic-profile-010.

Resource queries are stored in `data/evaluation/evaluation_cases.json` and copied to `artifacts/evaluation/test_case_inventory.json`.

Robustness cases:
| Case | Pass/Fail | Actual behavior |
| --- | --- | --- |
| missing_fields_profile | Pass | missing=['monthly_revenue', 'market_size_known', 'competition_understanding', 'revenue_model_clarity', 'process_automation_level', 'customer_retention'] |
| invalid_score_range_validation | Pass | ValidationError |
| llm_mock_fallback | Pass | Diagnostic summary: stage=IDEATION; blockers=0; prompt=Explain |
| expired_decryption_lease | Pass | LeaseExpired |
| unauthorized_project_route | Pass | 401 |

Anomaly cases:
| Case | Expected | Actual | Pass/Fail |
| --- | --- | --- | --- |
| high_traction_no_documented_evidence | high_traction_no_documented_evidence | high_traction_no_documented_evidence | Pass |
| manual_processes_limit_growth | manual_processes_limit_growth | high_traction_no_documented_evidence, manual_processes_limit_growth | Pass |
| high_innovation_claim_no_ip | high_innovation_claim_no_ip | high_innovation_claim_no_ip | Pass |
| revenue_without_mvp_artifact | revenue_without_mvp_artifact | revenue_without_mvp_artifact | Pass |
| high_sdg_without_practices | high_sdg_without_practices | high_sdg_without_practices | Pass |

## Appendix B — Raw Results

Raw machine-readable results are available in `artifacts/evaluation/`. Key compact excerpts:

```json
{
  "maturity_accuracy": 0.49,
  "maturity_macro_f1": 0.4074206175007316,
  "high_risk_false_ready_rate": 0.17,
  "blocker_micro_f1": 0.817391304347826,
  "blocker_macro_f1": 0.7581699346405228,
  "score_reproducibility_rate": 1.0,
  "lambda_penalty_correctness_rate": 1.0,
  "market_score_mae_against_synthetic_hint": 25.025,
  "scalability_score_mae_against_synthetic_hint": 11.082952500000001,
  "anomaly_detection_accuracy": 1.0,
  "anomaly_false_alert_rate": 0.0,
  "resource_precision_at_3": 0.5833333333333334,
  "resource_recall_at_3": 0.625,
  "resource_mrr": 0.75,
  "source_grounding_rate": 1.0,
  "eligibility_rule_accuracy": 0.8,
  "roadmap_grounding_rate": 1.0,
  "robustness_no_crash_rate": 1.0,
  "security_encryption_round_trip_pass": true
}
```

Confusion matrix:

| actual\predicted | IDEATION | MARKET_VALIDATION | STRUCTURATION | FUNDRAISING | LAUNCH_PLANNING | GROWTH |
| --- | --- | --- | --- | --- | --- | --- |
| IDEATION | 17 | 0 | 0 | 0 | 0 | 0 |
| MARKET_VALIDATION | 0 | 9 | 0 | 8 | 0 | 0 |
| STRUCTURATION | 0 | 8 | 0 | 0 | 0 | 9 |
| FUNDRAISING | 0 | 0 | 0 | 7 | 0 | 10 |
| LAUNCH_PLANNING | 0 | 0 | 0 | 0 | 0 | 16 |
| GROWTH | 0 | 0 | 0 | 0 | 0 | 16 |

## Appendix C — Evidence Mapping

| Claim | Evidence |
| --- | --- |
| Repository structure and service boundaries | `ARCHITECTURE.md`, `docs/architecture.md`, `services/*/README.md` |
| Scoring method and score names | `shared/domain/scoring.py`, `services/scoring_service/README.md` |
| Maturity stages and rule-based predictor | `shared/domain/maturity.py`, `tests/unit/test_maturity.py` |
| Blocker labels and metrics | `data/synthetic/blocker_labels.csv`, `shared/domain/blockers.py` |
| Anomaly rules | `shared/domain/scoring.py`, `artifacts/evaluation/test_case_inventory.json` |
| Resource corpus and MVP matching | `data/knowledge_base/resources.json`, `shared/domain/resources.py` |
| Eligibility | `shared/domain/eligibility.py`, `tests/unit/test_eligibility.py` |
| Roadmap grounding | `shared/domain/roadmap.py`, `services/roadmap_service/app/generator.py`, `tests/unit/test_generated_roadmap.py` |
| Authentication and 2FA | `services/api_gateway/app/auth`, `tests/unit/test_auth.py` |
| Encryption and decryption lease | `shared/security/encryption.py`, `shared/security/leases.py`, `tests/unit/test_security.py` |
| Evaluation scripts | `scripts/run_evaluation.py`, `scripts/run_performance_benchmark.py`, `scripts/generate_evaluation_report_data.py` |
| Presentation files | No `.ppt`, `.pptx`, `.pdf`, or `.docx` file found during local inspection. |
