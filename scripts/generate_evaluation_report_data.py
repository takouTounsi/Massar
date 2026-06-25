"""Generate the Massar evaluation report from measured evaluation artifacts."""

from __future__ import annotations

import csv
import json
import textwrap
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "evaluation"
DOCS_DIR = ROOT / "docs"

RESULTS_PATH = ARTIFACT_DIR / "results.json"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"
LATENCY_PATH = ARTIFACT_DIR / "latency_results.json"
INVENTORY_PATH = ARTIFACT_DIR / "test_case_inventory.json"
CONFUSION_PATH = ARTIFACT_DIR / "confusion_matrix.csv"
REPORT_MD_PATH = DOCS_DIR / "evaluation_report.md"
REPORT_PDF_PATH = DOCS_DIR / "evaluation_report.pdf"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fmt_num(value: Any, digits: int = 3) -> str:
    if value is None:
        return "Not measured"
    if isinstance(value, bool):
        return "Pass" if value else "Fail"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def fmt_pct(value: Any, digits: int = 1) -> str:
    if value is None:
        return "Not measured"
    if isinstance(value, bool):
        return "100.0%" if value else "0.0%"
    if isinstance(value, (int, float)):
        return f"{value * 100:.{digits}f}%"
    return str(value)


def escape_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(cell) for cell in row) + " |")
    return lines


def pass_fail(value: Any) -> str:
    return "Pass" if value else "Fail"


def read_confusion_matrix() -> list[list[str]]:
    if not CONFUSION_PATH.exists():
        return []
    with CONFUSION_PATH.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.reader(handle))


def not_measured_block(key: str, item: dict[str, str]) -> list[str]:
    title = key.replace("_", " ").title()
    return [
        f"- **{title}**",
        f"  Status: {item.get('status', 'Not measured in current MVP')}",
        f"  Reason: {item.get('reason', 'No reason recorded.')}",
        f"  Recommended next step: {item.get('recommended_next_step', 'Define and implement an evaluation harness.')}",
    ]


def build_report(results: dict[str, Any], metrics: dict[str, Any], latency: dict[str, Any], inventory: dict[str, Any]) -> str:
    dataset = results["dataset"]
    maturity = results["maturity"]
    blockers = results["blockers"]
    scoring = results["scoring"]
    anomalies = results["anomalies"]
    resources = results["resources"]
    roadmap = results["roadmap"]
    robustness = results["robustness"]
    security = results["security"]
    not_measured = results["not_measured"]

    lines: list[str] = [
        "# Massar",
        "## Evaluation Report",
        "### Metrics, Test Protocol, Results and Limitations",
        "",
        f"Generated on {date.today().isoformat()} from local repository artifacts.",
        "",
        "## 1. Executive Summary",
        "",
        "Massar is evaluated as a deterministic, evidence-aware entrepreneurial orientation system. The current MVP does not predict long-term startup success; it evaluates stage readiness, maturity diagnosis, score consistency, blockers, evidence confidence, anomaly detection, roadmap grounding, resource matching, eligibility, security behavior, and robustness under incomplete or contradictory inputs.",
        "",
        "The evaluation uses the current executable code, synthetic fixtures, local JSON resources, unit/integration tests, and generated artifacts. No PowerPoint, PDF, DOCX, or pitch deck file was found in the repository workspace during inspection, so product context came from `README.md`, `ARCHITECTURE.md`, and Markdown documents under `docs/`.",
        "",
    ]

    lines.extend(
        table(
            ["Area", "Measured result", "Source"],
            [
                ["Maturity diagnosis", f"Accuracy {fmt_pct(maturity['accuracy'])}; Macro F1 {fmt_num(maturity['macro_f1'])}", "`artifacts/evaluation/results.json`"],
                ["Blocker detection", f"Micro F1 {fmt_num(blockers['micro_f1'])}; Macro F1 {fmt_num(blockers['macro_f1'])}", "`scripts/run_evaluation.py`"],
                ["Scoring reproducibility", fmt_pct(scoring["reproducibility_rate"]), "`shared/domain/scoring.py`"],
                ["Lambda penalty correctness", fmt_pct(scoring["lambda_penalty_correctness_rate"]), "`artifacts/evaluation/metrics.json`"],
                ["Anomaly rules", f"Accuracy {fmt_pct(anomalies['anomaly_detection_accuracy'])}; false-alert rate {fmt_pct(anomalies['false_alert_rate_on_clean_case'])}", "`artifacts/evaluation/test_case_inventory.json`"],
                ["MVP resource matching", f"Precision@3 {fmt_num(resources['precision_at_3'])}; Recall@3 {fmt_num(resources['recall_at_3'])}; MRR {fmt_num(resources['mrr'])}", "`data/evaluation/evaluation_cases.json`"],
                ["Roadmap grounding", fmt_pct(roadmap["roadmap_grounding_rate"]), "`shared/domain/roadmap.py`"],
                ["Robustness", f"No-crash rate {fmt_pct(robustness['no_crash_rate'])}", "`scripts/run_evaluation.py`"],
                ["Security encryption check", pass_fail(security["aes_gcm_round_trip_pass"]), "`tests/unit/test_security.py`"],
            ],
        )
    )

    lines.extend(
        [
            "",
            "## 2. Evaluation Scope",
            "",
            "The evaluation covers the implemented MVP paths that can run locally without external services:",
            "",
            "- deterministic scoring and weighted readiness rules;",
            "- rule-based maturity diagnosis;",
            "- blocker and anomaly detection;",
            "- evidence and confidence behavior;",
            "- rule-based resource matching over the current local JSON corpus;",
            "- eligibility checks when metadata is available;",
            "- roadmap action grounding and dependency checks;",
            "- protected API route behavior for unauthenticated access;",
            "- AES-GCM encryption and temporary decryption lease behavior;",
            "- local in-process latency for scoring, resource matching, and full in-memory analysis.",
            "",
            "Out of scope for measured results: real entrepreneur outcomes, expert-labelled production data, production Docker latency, pgvector retrieval, SHAP explanations, and stable counterfactual action impact metrics. These are reported as not measured where applicable.",
            "",
            "## 3. System Components Evaluated",
            "",
        ]
    )

    lines.extend(
        table(
            ["Component type", "Implementation inspected", "Evaluation approach"],
            [
                ["Scoring engine", "`shared/domain/scoring.py`, `services/scoring_service`", "Formula consistency, reproducibility, penalty behavior, score hints"],
                ["Maturity diagnosis", "`shared/domain/maturity.py`, `services/maturity_service`", "Agreement with labelled synthetic maturity stages"],
                ["Blocker engine", "`shared/domain/blockers.py`, `services/blocker_service`", "Precision, recall, F1 on synthetic blocker labels"],
                ["Anomaly engine", "`shared/domain/scoring.py`", "Rule correctness and clean-case false-alert check"],
                ["Confidence", "`shared/domain/confidence.py`, evidence ledger hooks", "Missing-data visibility and confidence scaling"],
                ["Resource matching", "`shared/domain/resources.py`, `data/knowledge_base/resources.json`", "Precision@3, Recall@3, MRR, grounding"],
                ["Eligibility", "`shared/domain/eligibility.py`", "Rule status agreement where expected labels exist"],
                ["Roadmap", "`shared/domain/roadmap.py`, `services/roadmap_service`", "Grounding, resource validity, dependency compliance"],
                ["Security", "`shared/security`, `services/api_gateway/app/auth`", "Encryption round-trip, plaintext absence, lease expiry, protected route"],
                ["LLM layer", "`shared/llm`", "Fallback behavior only; not used for score correctness"],
            ],
        )
    )

    lines.extend(
        [
            "",
            "The current executable score names are `Market Score`, `Operational Score`, `Scalability Score`, `Innovation Score`, and `Green Score`. The report also notes one alignment risk: some frontend/demo documentation references `commercial_offer_score`, while the measured scoring engine emits `Operational Score`.",
            "",
            "## 4. Evaluation Dataset and Test Cases",
            "",
            "The dataset is explicitly marked as synthetic and is suitable for hackathon validation of deterministic behavior, not for real-world performance claims.",
            "",
        ]
    )

    lines.extend(
        table(
            ["Dataset item", "Count", "Source"],
            [
                ["Synthetic entrepreneur profiles", dataset["profile_count"], "`data/synthetic/entrepreneur_profiles.csv`"],
                ["Blocker labels", dataset["blocker_label_count"], "`data/synthetic/blocker_labels.csv`"],
                ["Scoring hints", dataset["scoring_hint_count"], "`data/synthetic/scoring_cases.csv`"],
                ["Resource query scenarios", dataset["resource_query_count"], "`data/evaluation/evaluation_cases.json`"],
                ["Roadmap profiles evaluated", roadmap["profiles_evaluated"], "`scripts/run_evaluation.py`"],
                ["Robustness cases", len(robustness["cases"]), "`artifacts/evaluation/test_case_inventory.json`"],
            ],
        )
    )

    lines.extend(
        [
            "",
            f"`synthetic_evaluation_dataset`: `{str(results['synthetic_evaluation_dataset']).lower()}`.",
            "",
            "## 5. Test Protocol",
            "",
            "The evaluation was run with deterministic local Python scripts. The protocol was:",
            "",
            "1. Load synthetic profiles, scoring hints, blocker labels, and resource query fixtures.",
            "2. Convert profile rows into `ProjectProfile` contracts.",
            "3. Run maturity, scoring, blocker, resource, eligibility, roadmap, robustness, and security checks using repository code.",
            "4. Write machine-readable artifacts to `artifacts/evaluation/`.",
            "5. Run a local in-process latency benchmark without LLM calls.",
            "6. Generate this Markdown and PDF report from the artifacts.",
            "",
            "Commands used:",
            "",
            "```powershell",
            "python scripts\\run_evaluation.py",
            "python scripts\\run_performance_benchmark.py",
            "python scripts\\generate_evaluation_report_data.py",
            "python -m pytest -q",
            "```",
            "",
            "## 6. Metrics",
            "",
            "Metric definitions used in the generated artifacts:",
            "",
        ]
    )

    lines.extend(
        table(
            ["Metric", "Definition"],
            [
                ["Maturity accuracy", "Correct diagnosed maturity labels divided by evaluated profiles."],
                ["Macro F1", "Unweighted mean of per-stage F1 scores."],
                ["High-risk false-ready rate", "Projects classified as Funding/Growth ready when expected labels indicate missing readiness evidence."],
                ["Blocker precision/recall/F1", "Multi-label blocker agreement against synthetic labels."],
                ["Score MAE", "Mean absolute error between deterministic score output and synthetic score hints."],
                ["Reproducibility rate", "Repeated deterministic scoring outputs that are identical."],
                ["Lambda penalty correctness", "Expected weakest-link penalty cases correctly penalized."],
                ["Anomaly detection accuracy", "Expected anomaly IDs detected in targeted scenarios."],
                ["False-alert rate", "Clean anomaly scenario producing unexpected anomaly output."],
                ["Precision@3", "Relevant returned resources in top three divided by three."],
                ["Recall@3", "Relevant returned resources in top three divided by expected relevant resources."],
                ["MRR", "Mean reciprocal rank of the first relevant resource."],
                ["Source grounding rate", "Returned resources that reference a known local resource source."],
                ["Roadmap grounding rate", "Actions linked to a blocker, weak score, maturity gap, or resource."],
                ["No-crash rate", "Robustness scenarios completed without unhandled failure."],
            ],
        )
    )

    lines.extend(["", "## 7. Results", "", "### 7.1 Maturity Diagnosis"])
    lines.extend(
        table(
            ["Metric", "Value"],
            [
                ["Accuracy", fmt_pct(maturity["accuracy"])],
                ["Macro F1", fmt_num(maturity["macro_f1"])],
                ["High-risk false-ready rate", fmt_pct(maturity["high_risk_false_ready_rate"])],
                ["High-risk false-ready count", maturity["high_risk_false_ready_count"]],
            ],
        )
    )

    per_label_rows = []
    for label, values in maturity["per_label"].items():
        per_label_rows.append(
            [
                label,
                fmt_num(values["precision"]),
                fmt_num(values["recall"]),
                fmt_num(values["f1"]),
                values["support"],
            ]
        )
    lines.extend(["", "Per-stage results:"])
    lines.extend(table(["Stage", "Precision", "Recall", "F1", "Support"], per_label_rows))

    lines.extend(["", "### 7.2 Scoring Engine"])
    lines.extend(
        table(
            ["Metric", "Value"],
            [
                ["Profiles scored", scoring["profiles"]],
                ["Score output count rate", fmt_pct(scoring["score_output_count_rate"])],
                ["Score name set", ", ".join(scoring["actual_score_name_sets"].keys())],
                ["Market Score MAE against synthetic hint", fmt_num(scoring["market_score_mae_against_synthetic_hint"])],
                ["Scalability Score MAE against synthetic hint", fmt_num(scoring["scalability_score_mae_against_synthetic_hint"])],
                ["Reproducibility rate", fmt_pct(scoring["reproducibility_rate"])],
                ["Lambda penalty correctness", fmt_pct(scoring["lambda_penalty_correctness_rate"])],
                ["Confidence ledger scaling", pass_fail(scoring["confidence_ledger_scaling_pass"])],
            ],
        )
    )

    lines.extend(["", "### 7.3 Blockers and Anomalies"])
    blocker_rows = []
    for label, values in blockers["per_label"].items():
        blocker_rows.append([label, values["tp"], values["fp"], values["fn"], fmt_num(values["precision"]), fmt_num(values["recall"]), fmt_num(values["f1"])])
    lines.extend(
        table(
            ["Blocker", "TP", "FP", "FN", "Precision", "Recall", "F1"],
            blocker_rows,
        )
    )
    lines.extend(
        [
            "",
            f"Overall blocker Micro F1: {fmt_num(blockers['micro_f1'])}. Overall blocker Macro F1: {fmt_num(blockers['macro_f1'])}.",
            "",
            "Anomaly scenario results:",
        ]
    )
    lines.extend(
        table(
            ["Test scenario", "Expected anomaly", "Actual output", "Pass/Fail", "Notes"],
            [
                [
                    case["case_id"],
                    case["expected"],
                    ", ".join(case["actual"]) or "none",
                    pass_fail(case["pass"]),
                    "Targeted rule scenario",
                ]
                for case in anomalies["cases"]
            ],
        )
    )
    lines.append(f"Clean-case false-alert rate: {fmt_pct(anomalies['false_alert_rate_on_clean_case'])}.")

    lines.extend(["", "### 7.4 Roadmap"])
    lines.extend(
        table(
            ["Metric", "Value"],
            [
                ["Profiles evaluated", roadmap["profiles_evaluated"]],
                ["Generated actions", roadmap["action_count"]],
                ["Roadmap grounding rate", fmt_pct(roadmap["roadmap_grounding_rate"])],
                ["Resource reference validity rate", fmt_pct(roadmap["resource_reference_validity_rate"])],
                ["Dependency compliance rate", fmt_pct(roadmap["dependency_compliance_rate"])],
                ["Counterfactual consistency rate", fmt_pct(roadmap["counterfactual_consistency_rate"])],
            ],
        )
    )
    lines.extend(
        [
            "",
            f"Counterfactual evaluation status: {roadmap['counterfactual_status']}. Reason: {roadmap['counterfactual_reason']}",
            "",
            "## 8. Robustness and Edge-Case Tests",
            "",
        ]
    )
    lines.extend(
        table(
            ["Edge case", "Expected behavior", "Actual behavior", "Pass/Fail"],
            [
                [case["case_id"], case["expected_behavior"], case["actual_behavior"], pass_fail(case["pass"])]
                for case in robustness["cases"]
            ],
        )
    )
    lines.extend(
        [
            "",
            f"No-crash rate: {fmt_pct(robustness['no_crash_rate'])}. Graceful degradation rate: {fmt_pct(robustness['graceful_degradation_rate'])}. Fallback success rate: {fmt_pct(robustness['fallback_success_rate'])}.",
            "",
            "## 9. RAG and Resource Matching Evaluation",
            "",
            "The current runnable MVP uses rule-based metadata/lexical resource matching over `data/knowledge_base/resources.json`. It is not a full vector RAG benchmark because no active vector retrieval or reranker endpoint was executed by the evaluation script.",
            "",
        ]
    )
    lines.extend(
        table(
            ["Metric", "Value"],
            [
                ["Measured query count", resources["measured_query_count"]],
                ["Precision@3", fmt_num(resources["precision_at_3"])],
                ["Recall@3", fmt_num(resources["recall_at_3"])],
                ["MRR", fmt_num(resources["mrr"])],
                ["Source grounding rate", fmt_pct(resources["source_grounding_rate"])],
                ["Eligibility rule accuracy", fmt_pct(resources["eligibility_rule_accuracy"])],
            ],
        )
    )
    lines.extend(["", "Resource query results:"])
    lines.extend(
        table(
            ["Case", "Measured", "Expected IDs", "Returned IDs", "P@3", "R@3", "MRR", "Not measured reason"],
            [
                [
                    case["case_id"],
                    str(case["measured"]).lower(),
                    ", ".join(case["expected_relevant_resource_ids"]),
                    ", ".join(case["returned_resource_ids"]),
                    fmt_num(case["precision_at_3"]),
                    fmt_num(case["recall_at_3"]),
                    fmt_num(case["reciprocal_rank"]),
                    case.get("not_measured_reason") or "",
                ]
                for case in resources["queries"]
            ],
        )
    )

    lines.extend(
        [
            "",
            "## 10. Performance and Latency Evaluation",
            "",
            f"Benchmark note: {latency['benchmark_metadata']['note']}",
            "",
        ]
    )
    lines.extend(
        table(
            ["Operation", "Environment", "Runs", "p50 ms", "p95 ms", "Error rate", "LLM enabled", "Data source"],
            [
                [
                    op["operation"],
                    op["environment"],
                    op["runs"],
                    fmt_num(op["p50_ms"]),
                    fmt_num(op["p95_ms"]),
                    fmt_pct(op["error_rate"]),
                    str(op["llm_enabled"]).lower(),
                    op["data_source"],
                ]
                for op in latency["operations"]
            ],
        )
    )

    lines.extend(
        [
            "",
            "Production latency:",
        ]
    )
    lines.extend(not_measured_block("production_latency", not_measured["production_latency"]))

    lines.extend(
        [
            "",
            "## 11. Explainability Evaluation",
            "",
            "The MVP exposes explainability through deterministic score decomposition, blocker reasons, missing-data visibility, resource source references, and roadmap rationales. The measured explainability checks are structural and grounding-oriented rather than SHAP-based.",
            "",
        ]
    )
    lines.extend(
        table(
            ["Explainability area", "Measured result", "Evidence"],
            [
                ["Score traceability", "Implemented structurally through score breakdown fields", "`shared/domain/scoring.py`"],
                ["Diagnostic justification coverage", "Covered indirectly by maturity/blocker outputs and missing-field checks", "`shared/domain/maturity.py`, `shared/domain/confidence.py`"],
                ["Source grounding", fmt_pct(resources["source_grounding_rate"]), "`artifacts/evaluation/results.json`"],
                ["Roadmap coherence", fmt_pct(roadmap["roadmap_grounding_rate"]), "`artifacts/evaluation/results.json`"],
                ["Confidence visibility", pass_fail(scoring["confidence_ledger_scaling_pass"]), "`scripts/run_evaluation.py`"],
                ["SHAP availability", "Not measured", "`docs/ml-strategy.md`, `shared/domain/maturity.py`"],
            ],
        )
    )
    lines.extend(
        [
            "",
            "SHAP is documented as a planned explainability mechanism for ML-backed services. It was not evaluated in the current rule-based MVP because no trained ML model was executed.",
            "",
        ]
    )
    lines.extend(not_measured_block("shap_availability_rate", not_measured["shap_availability_rate"]))

    lines.extend(
        [
            "",
            "## 12. Limitations",
            "",
            "The following limitations are supported by the current repository state and generated artifacts:",
            "",
            "- The evaluation dataset is synthetic; there are no expert-labelled real entrepreneur profiles yet.",
            "- Maturity and scoring behavior are currently deterministic/rule-based for the measured MVP paths.",
            "- The local resource corpus is small, and one public-procurement test scenario was not measurable because no matching corpus item exists.",
            "- The executable resource matching evaluation is MVP rule-based matching, not vector RAG.",
            "- Production-scale latency through Docker Compose, PostgreSQL, and pgvector was not measured.",
            "- SHAP and trained ML model explanations are documented/planned but were not executed.",
            "- The counterfactual engine exists in `shared/domain/scoring_intelligence.py`, but its action-impact evaluation is not exposed through a stable measured service endpoint.",
            "- Authentication, encryption, and decryption leases are MVP-level checks, not a production KMS/Vault deployment.",
            "- Some demo/documentation naming still references `commercial_offer_score`, while the measured scoring engine emits `Operational Score`.",
            "",
            "Additional not-measured items:",
        ]
    )
    for key, value in not_measured.items():
        if key not in {"production_latency", "shap_availability_rate"}:
            lines.extend(not_measured_block(key, value))

    lines.extend(
        [
            "",
            "## 13. Reproducibility Instructions",
            "",
            "From the repository root:",
            "",
            "```powershell",
            "python -m pytest -q",
            "python scripts\\run_evaluation.py",
            "python scripts\\run_performance_benchmark.py",
            "python scripts\\generate_evaluation_report_data.py",
            "```",
            "",
            "Generated artifacts:",
            "",
            "- `artifacts/evaluation/results.json`",
            "- `artifacts/evaluation/metrics.json`",
            "- `artifacts/evaluation/confusion_matrix.csv`",
            "- `artifacts/evaluation/test_case_inventory.json`",
            "- `artifacts/evaluation/latency_results.json`",
            "- `docs/evaluation_report.md`",
            "- `docs/evaluation_report.pdf`",
            "",
            "No plots were generated because the report generator intentionally uses only the standard library and does not fabricate chart images.",
            "",
            "## 14. Conclusion",
            "",
            "The current Massar MVP has a reproducible evaluation harness for its deterministic orientation pipeline. It demonstrates measurable behavior for maturity diagnosis, scoring reproducibility, blocker detection, anomaly rules, MVP resource matching, roadmap grounding, robustness, authentication protection, and encryption lease behavior.",
            "",
            "The strongest measured areas are deterministic reproducibility, lambda penalty correctness, targeted anomaly rule detection, roadmap grounding, robustness, and encryption checks. The weakest measured areas are maturity macro F1 and resource matching consistency on the small synthetic corpus. The main next step is to add expert-labelled real cases, a larger resource corpus, production benchmarks, stable counterfactual fixtures, and executable ML/RAG explainability evaluation.",
            "",
            "## Appendix A — Test Case Inventory",
            "",
            f"Maturity profile IDs evaluated: {len(inventory['maturity_profile_ids'])}. First ten: {', '.join(inventory['maturity_profile_ids'][:10])}.",
            "",
            "Resource queries are stored in `data/evaluation/evaluation_cases.json` and copied to `artifacts/evaluation/test_case_inventory.json`.",
            "",
            "Robustness cases:",
        ]
    )
    lines.extend(
        table(
            ["Case", "Pass/Fail", "Actual behavior"],
            [[case["case_id"], pass_fail(case["pass"]), case["actual_behavior"]] for case in inventory["robustness_cases"]],
        )
    )
    lines.extend(["", "Anomaly cases:"])
    lines.extend(
        table(
            ["Case", "Expected", "Actual", "Pass/Fail"],
            [[case["case_id"], case["expected"], ", ".join(case["actual"]), pass_fail(case["pass"])] for case in inventory["anomaly_cases"]],
        )
    )

    confusion = read_confusion_matrix()
    lines.extend(["", "## Appendix B — Raw Results", ""])
    lines.extend(
        [
            "Raw machine-readable results are available in `artifacts/evaluation/`. Key compact excerpts:",
            "",
            "```json",
            json.dumps(metrics, indent=2),
            "```",
            "",
            "Confusion matrix:",
            "",
        ]
    )
    if confusion:
        headers = confusion[0]
        rows = confusion[1:]
        lines.extend(table(headers, rows))
    else:
        lines.append("Confusion matrix artifact was not found.")

    lines.extend(
        [
            "",
            "## Appendix C — Evidence Mapping",
            "",
        ]
    )
    lines.extend(
        table(
            ["Claim", "Evidence"],
            [
                ["Repository structure and service boundaries", "`ARCHITECTURE.md`, `docs/architecture.md`, `services/*/README.md`"],
                ["Scoring method and score names", "`shared/domain/scoring.py`, `services/scoring_service/README.md`"],
                ["Maturity stages and rule-based predictor", "`shared/domain/maturity.py`, `tests/unit/test_maturity.py`"],
                ["Blocker labels and metrics", "`data/synthetic/blocker_labels.csv`, `shared/domain/blockers.py`"],
                ["Anomaly rules", "`shared/domain/scoring.py`, `artifacts/evaluation/test_case_inventory.json`"],
                ["Resource corpus and MVP matching", "`data/knowledge_base/resources.json`, `shared/domain/resources.py`"],
                ["Eligibility", "`shared/domain/eligibility.py`, `tests/unit/test_eligibility.py`"],
                ["Roadmap grounding", "`shared/domain/roadmap.py`, `services/roadmap_service/app/generator.py`, `tests/unit/test_generated_roadmap.py`"],
                ["Authentication and 2FA", "`services/api_gateway/app/auth`, `tests/unit/test_auth.py`"],
                ["Encryption and decryption lease", "`shared/security/encryption.py`, `shared/security/leases.py`, `tests/unit/test_security.py`"],
                ["Evaluation scripts", "`scripts/run_evaluation.py`, `scripts/run_performance_benchmark.py`, `scripts/generate_evaluation_report_data.py`"],
                ["Presentation files", "No `.ppt`, `.pptx`, `.pdf`, or `.docx` file found during local inspection."],
            ],
        )
    )

    return "\n".join(lines).rstrip() + "\n"


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def markdown_to_pdf_lines(markdown: str) -> list[str]:
    out: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            out.append("")
            continue
        line = line.replace("`", "")
        line = line.replace("**", "")
        line = line.replace("# ", "")
        line = line.replace("## ", "")
        line = line.replace("### ", "")
        line = line.replace("—", "-")
        wrapped = textwrap.wrap(line, width=96, replace_whitespace=False) or [""]
        out.extend(wrapped)
    return out


def write_simple_pdf(markdown: str, path: Path) -> None:
    lines = markdown_to_pdf_lines(markdown)
    page_size = 48
    pages = [lines[i : i + page_size] for i in range(0, len(lines), page_size)] or [[]]

    objects: list[bytes] = []
    page_ids = [4 + i * 2 for i in range(len(pages))]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for index, page_lines in enumerate(pages):
        page_id = page_ids[index]
        content_id = page_id + 1
        page_object = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        )
        commands = ["BT", "/F1 9 Tf", "50 760 Td", "12 TL"]
        for line in page_lines:
            safe = pdf_escape(line.encode("latin-1", errors="replace").decode("latin-1"))
            commands.append(f"({safe}) Tj")
            commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1")
        content_object = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        objects.append(page_object.encode("ascii"))
        objects.append(content_object)

    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for object_number, payload in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{object_number} 0 obj\n".encode("ascii"))
        chunks.append(payload)
        chunks.append(b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    chunks.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(b"".join(chunks))


def main() -> None:
    results = load_json(RESULTS_PATH)
    metrics = load_json(METRICS_PATH)
    latency = load_json(LATENCY_PATH)
    inventory = load_json(INVENTORY_PATH)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report(results, metrics, latency, inventory)
    REPORT_MD_PATH.write_text(report, encoding="utf-8")
    write_simple_pdf(report, REPORT_PDF_PATH)

    print(
        json.dumps(
            {
                "markdown_report": str(REPORT_MD_PATH.relative_to(ROOT)),
                "pdf_report": str(REPORT_PDF_PATH.relative_to(ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
