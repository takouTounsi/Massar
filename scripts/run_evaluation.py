from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any
from uuid import uuid5, NAMESPACE_URL

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from services.api_gateway.app.main import app as gateway_app
from shared.application import InMemoryOrientationPipeline
from shared.contracts.enums import BusinessType, CountryCode, MaturityStage
from shared.contracts.schemas import ProjectCreateRequest, ProjectProfile
from shared.domain.blockers import RuleBasedBlockerDetector
from shared.domain.confidence import assess_confidence
from shared.domain.eligibility import evaluate_eligibility
from shared.domain.maturity import RuleBasedMaturityPredictor
from shared.domain.resources import match_resources
from shared.domain.roadmap import build_roadmap
from shared.domain.scoring import LAMBDA_DEFAULT, WeightedRuleScoreCalculator
from shared.llm import MockLLMProvider
from shared.security import DataEncryptor, LeaseExpired
from shared.security.leases import DecryptionLeaseManager

ARTIFACT_DIR = ROOT / "artifacts" / "evaluation"
SYNTHETIC_DIR = ROOT / "data" / "synthetic"
EVAL_CASES = ROOT / "data" / "evaluation" / "evaluation_cases.json"
STAGES = [stage.value for stage in MaturityStage]
BLOCKER_LABELS = ["MARKET_VALIDATION_BLOCKER", "TENDER_READINESS_BLOCKER", "SCALABILITY_BLOCKER"]


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    return int(float(value))


def _float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    return float(value)


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _profile_from_row(row: dict[str, str]) -> ProjectProfile:
    paying = _int(row.get("paying_customers"))
    interviews = _int(row.get("documented_interviews"))
    has_revenue = _bool(row.get("has_revenue")) or paying > 0
    evidence: list[str] = []
    # Keep this conservative: only explicit revenue/customer count is treated as traction.
    if paying > 0 and interviews >= 10:
        evidence = ["synthetic_interview_summary"]
    return ProjectProfile(
        project_id=uuid5(NAMESPACE_URL, row["project_id"]),
        country=CountryCode(row.get("country") or "TN"),
        business_type=BusinessType(row.get("business_type") or "startup"),
        sector=row.get("sector") or "technology",
        declared_stage=MaturityStage(row.get("declared_stage") or "IDEATION"),
        primary_goal=row.get("primary_goal") or None,
        has_mvp=_bool(row.get("has_mvp")),
        has_revenue=has_revenue,
        monthly_revenue=float(paying * 500) if has_revenue else 0.0,
        paying_customers=paying,
        documented_interviews=interviews,
        market_validation_evidence=evidence,
        process_automation_level=_float(row.get("process_automation_level")),
        wants_public_tenders=_bool(row.get("wants_public_tenders")),
        administrative_documents_ready=_bool(row.get("administrative_documents_ready")),
        financial_capacity_score=_int(row.get("financial_capacity_score")),
        market_size_known=interviews >= 15,
        competition_understanding=min(100, 35 + interviews * 2),
        revenue_model_clarity=70 if has_revenue else 35,
        team_size=3 if row.get("business_type") == "startup" else 5,
        tech_stack_scalability=int(_float(row.get("process_automation_level")) * 100),
        infrastructure_readiness=int(_float(row.get("process_automation_level")) * 100),
        problem_novelty_score=65 if row.get("business_type") == "startup" else 45,
        technology_readiness_level=5 if _bool(row.get("has_mvp")) else 2,
        process_documentation_score=int(_float(row.get("process_automation_level")) * 100),
        financial_model_quality=_int(row.get("financial_capacity_score")),
        legal_compliance_score=80 if _bool(row.get("administrative_documents_ready")) else 35,
    )


def _profile_from_case(data: dict[str, Any], seed: str) -> ProjectProfile:
    payload = dict(data)
    payload.setdefault("project_id", uuid5(NAMESPACE_URL, seed))
    if "country" in payload:
        payload["country"] = CountryCode(payload["country"])
    if "business_type" in payload:
        payload["business_type"] = BusinessType(payload["business_type"])
    if "declared_stage" in payload:
        payload["declared_stage"] = MaturityStage(payload["declared_stage"])
    return ProjectProfile(**payload)


def _classification_metrics(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict[str, Any]:
    matrix = {true: {pred: 0 for pred in labels} for true in labels}
    for true, pred in zip(y_true, y_pred, strict=True):
        matrix[true][pred] += 1
    per_label: dict[str, dict[str, float]] = {}
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in labels if other != label)
        fn = sum(matrix[label][other] for other in labels if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(matrix[label].values())}
    accuracy = sum(1 for a, b in zip(y_true, y_pred, strict=True) if a == b) / len(y_true) if y_true else 0.0
    return {
        "accuracy": accuracy,
        "macro_f1": statistics.mean(item["f1"] for item in per_label.values()),
        "per_label": per_label,
        "confusion_matrix": matrix,
    }


def _multilabel_metrics(expected_rows: list[dict[str, int]], actual_rows: list[dict[str, int]]) -> dict[str, Any]:
    per_label: dict[str, dict[str, float | int]] = {}
    total_tp = total_fp = total_fn = 0
    for label in BLOCKER_LABELS:
        tp = fp = fn = tn = 0
        for expected, actual in zip(expected_rows, actual_rows, strict=True):
            e = expected[label]
            a = actual[label]
            if e and a:
                tp += 1
            elif not e and a:
                fp += 1
            elif e and not a:
                fn += 1
            else:
                tn += 1
        total_tp += tp
        total_fp += fp
        total_fn += fn
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1}
    micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if micro_precision + micro_recall else 0.0
    return {
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": micro_f1,
        "macro_f1": statistics.mean(float(item["f1"]) for item in per_label.values()),
        "per_label": per_label,
    }


def _score_metrics(profiles: list[ProjectProfile], scoring_rows: list[dict[str, str]]) -> dict[str, Any]:
    calc = WeightedRuleScoreCalculator()
    exact_repro = 0
    output_count_ok = 0
    lambda_cases = 0
    lambda_pass = 0
    market_errors: list[float] = []
    scalability_errors: list[float] = []
    expected_by_id = {row["case_id"]: row for row in scoring_rows}
    expected_score_names = {"Market Score", "Scalability Score", "Innovation Score", "Operational Score", "Green Score"}
    actual_score_name_sets: dict[str, int] = {}

    for profile, row in zip(profiles, scoring_rows, strict=True):
        first = calc.calculate(profile)
        second = calc.calculate(profile)
        if first.model_dump(mode="json") == second.model_dump(mode="json"):
            exact_repro += 1
        names = {score.name for score in first.scores}
        actual_score_name_sets[", ".join(sorted(names))] = actual_score_name_sets.get(", ".join(sorted(names)), 0) + 1
        if names == expected_score_names:
            output_count_ok += 1
        by_name = first.by_name()
        market_errors.append(abs(by_name["market_score"].value - float(row["market_score_hint"])))
        scalability_errors.append(abs(by_name["scalability_score"].value - float(row["scalability_score_hint"])))
        for score in first.scores:
            fundamentals = [sub for sub in score.sub_scores if sub.fundamental and sub.name not in score.missing_criteria]
            if not fundamentals:
                continue
            base = sum(sub.contribution for sub in score.sub_scores)
            min_fundamental = min(sub.value / 100.0 for sub in fundamentals)
            expected_value = max(0.0, min(100.0, base * (1 - LAMBDA_DEFAULT * (1 - min_fundamental))))
            lambda_cases += 1
            if abs(score.value - expected_value) <= 1e-6:
                lambda_pass += 1

    base_profile = profiles[0]
    base_conf = calc.calculate(base_profile).by_name()["market_score"].confidence
    from shared.contracts.enums import EvidenceStatus
    from shared.intake.contracts import LedgerEntry
    ledger = {
        "paying_customers": LedgerEntry(field="paying_customers", value=base_profile.paying_customers, status=EvidenceStatus.UNVERIFIED),
        "market_size_known": LedgerEntry(field="market_size_known", value=base_profile.market_size_known, status=EvidenceStatus.UNVERIFIED),
    }
    scaled_conf = calc.calculate_with_ledger(base_profile, ledger).by_name()["market_score"].confidence

    return {
        "profiles": len(profiles),
        "score_output_count_rate": output_count_ok / len(profiles),
        "actual_score_name_sets": actual_score_name_sets,
        "market_score_mae_against_synthetic_hint": statistics.mean(market_errors),
        "scalability_score_mae_against_synthetic_hint": statistics.mean(scalability_errors),
        "reproducibility_rate": exact_repro / len(profiles),
        "lambda_penalty_correctness_rate": lambda_pass / lambda_cases if lambda_cases else None,
        "lambda_penalty_cases": lambda_cases,
        "confidence_ledger_scaling_pass": scaled_conf < base_conf,
        "confidence_ledger_scaling_base": base_conf,
        "confidence_ledger_scaling_unverified": scaled_conf,
    }


def _anomaly_metrics() -> dict[str, Any]:
    calc = WeightedRuleScoreCalculator()
    cases = [
        ("high_traction_no_documented_evidence", ProjectProfile(paying_customers=6, has_mvp=True, has_revenue=True, market_validation_evidence=[], declared_stage=MaturityStage.GROWTH)),
        ("manual_processes_limit_growth", ProjectProfile(declared_stage=MaturityStage.GROWTH, has_mvp=True, has_revenue=True, paying_customers=12, process_automation_level=0.2)),
        ("high_innovation_claim_no_ip", ProjectProfile(problem_novelty_score=90, ip_assets=[])),
        ("revenue_without_mvp_artifact", ProjectProfile(paying_customers=1, has_mvp=False)),
        ("high_sdg_without_practices", ProjectProfile(sdg_alignment_score=90, green_practices=[])),
    ]
    rows = []
    detected = 0
    for expected, profile in cases:
        actual = sorted({item for score in calc.calculate(profile).scores for item in score.anomalies})
        ok = expected in actual
        detected += int(ok)
        rows.append({"case_id": expected, "expected": expected, "actual": actual, "pass": ok})
    clean = ProjectProfile(has_mvp=True, has_revenue=True, paying_customers=2, market_validation_evidence=["invoice", "interview"], problem_novelty_score=40, ip_assets=["trade_secret"], process_automation_level=0.7, declared_stage=MaturityStage.FUNDRAISING, sdg_alignment_score=30, green_practices=["recycling"])
    clean_anomalies = [item for score in calc.calculate(clean).scores for item in score.anomalies]
    return {
        "cases": rows,
        "anomaly_detection_accuracy": detected / len(cases),
        "false_alert_rate_on_clean_case": 1.0 if clean_anomalies else 0.0,
        "clean_case_anomalies": clean_anomalies,
    }


def _resource_metrics(cases: dict[str, Any]) -> dict[str, Any]:
    rows = []
    precision_values: list[float] = []
    recall_values: list[float] = []
    mrr_values: list[float] = []
    source_grounded = 0
    source_total = 0
    eligibility_expected = 0
    eligibility_correct = 0
    predictor = RuleBasedMaturityPredictor()
    scorer = WeightedRuleScoreCalculator()
    blocker_detector = RuleBasedBlockerDetector()

    for case in cases["resource_queries"]:
        profile = _profile_from_case(case["profile"], case["case_id"])
        maturity = predictor.predict(profile)
        scores = scorer.calculate(profile)
        blockers = blocker_detector.detect(profile, maturity)
        resources = match_resources(profile, maturity, scores, blockers, limit=3)
        eligibility = evaluate_eligibility(profile, resources)
        returned = [resource.resource_id for resource in resources]
        expected = case.get("expected_relevant_resource_ids", [])
        measured = bool(expected)
        relevant_returned = len(set(returned) & set(expected)) if measured else 0
        precision = relevant_returned / len(returned) if measured and returned else None
        recall = relevant_returned / len(expected) if measured and expected else None
        rr = None
        if measured:
            rr = 0.0
            for index, resource_id in enumerate(returned, start=1):
                if resource_id in expected:
                    rr = 1.0 / index
                    break
            precision_values.append(float(precision or 0.0))
            recall_values.append(float(recall or 0.0))
            mrr_values.append(float(rr or 0.0))
        for resource in resources:
            source_total += 1
            if resource.source_url and resource.source_chunk_ids:
                source_grounded += 1
        expected_statuses = case.get("expected_eligibility_statuses", {})
        status_by_resource = {item.resource_id: str(item.status) for item in eligibility}
        for resource_id, expected_status in expected_statuses.items():
            eligibility_expected += 1
            eligibility_correct += int(status_by_resource.get(resource_id) == expected_status)
        rows.append({
            "case_id": case["case_id"],
            "description": case["description"],
            "measured": measured,
            "not_measured_reason": case.get("not_measured_reason"),
            "expected_relevant_resource_ids": expected,
            "returned_resource_ids": returned,
            "precision_at_3": precision,
            "recall_at_3": recall,
            "reciprocal_rank": rr,
            "eligibility_statuses": status_by_resource,
        })
    return {
        "queries": rows,
        "measured_query_count": len(precision_values),
        "precision_at_3": statistics.mean(precision_values) if precision_values else None,
        "recall_at_3": statistics.mean(recall_values) if recall_values else None,
        "mrr": statistics.mean(mrr_values) if mrr_values else None,
        "source_grounding_rate": source_grounded / source_total if source_total else None,
        "eligibility_rule_accuracy": eligibility_correct / eligibility_expected if eligibility_expected else None,
        "eligibility_expected_cases": eligibility_expected,
    }


def _roadmap_metrics(profiles: list[ProjectProfile]) -> dict[str, Any]:
    predictor = RuleBasedMaturityPredictor()
    scorer = WeightedRuleScoreCalculator()
    blocker_detector = RuleBasedBlockerDetector()
    action_count = grounded = valid_resources = dependency_ok = 0
    errors = 0
    for profile in profiles[:25]:
        try:
            maturity = predictor.predict(profile)
            scores = scorer.calculate(profile)
            blockers = blocker_detector.detect(profile, maturity)
            resources = match_resources(profile, maturity, scores, blockers)
            eligibility = evaluate_eligibility(profile, resources)
            roadmap = build_roadmap(profile, blockers, scores, resources, eligibility)
            resource_ids = {resource.resource_id for resource in resources}
            seen_actions: set[str] = set()
            for action in roadmap.actions:
                action_count += 1
                if action.addresses_blocker_ids or action.addresses_score or action.rationale:
                    grounded += 1
                if set(action.resource_ids).issubset(resource_ids):
                    valid_resources += 1
                if set(action.depends_on).issubset(seen_actions):
                    dependency_ok += 1
                seen_actions.add(action.id)
        except Exception:
            errors += 1
    return {
        "profiles_evaluated": min(25, len(profiles)),
        "action_count": action_count,
        "roadmap_grounding_rate": grounded / action_count if action_count else 0.0,
        "resource_reference_validity_rate": valid_resources / action_count if action_count else 0.0,
        "dependency_compliance_rate": dependency_ok / action_count if action_count else 0.0,
        "generation_error_count": errors,
        "counterfactual_consistency_rate": None,
        "counterfactual_status": "Not measured in current MVP",
        "counterfactual_reason": "CounterfactualEngine exists in shared/domain/scoring_intelligence.py but is not covered by a stable service endpoint or test fixture in the current runnable MVP.",
    }


def _robustness_metrics() -> dict[str, Any]:
    cases = []
    def record(case_id: str, expected: str, ok: bool, actual: str) -> None:
        cases.append({"case_id": case_id, "expected_behavior": expected, "actual_behavior": actual, "pass": ok})

    try:
        profile = ProjectProfile(country=CountryCode.TN, business_type=BusinessType.STARTUP, declared_stage=MaturityStage.IDEATION)
        maturity = RuleBasedMaturityPredictor().predict(profile)
        scores = WeightedRuleScoreCalculator().calculate(profile)
        blockers = RuleBasedBlockerDetector().detect(profile, maturity)
        confidence = assess_confidence(profile, maturity, scores, blockers)
        record("missing_fields_profile", "No crash; missing fields visible", bool(confidence.missing_fields), f"missing={confidence.missing_fields}")
    except Exception as exc:
        record("missing_fields_profile", "No crash; missing fields visible", False, repr(exc))

    try:
        ProjectProfile(competition_understanding=200)
        record("invalid_score_range_validation", "Pydantic rejects invalid score range", False, "accepted invalid value")
    except Exception as exc:
        record("invalid_score_range_validation", "Pydantic rejects invalid score range", True, exc.__class__.__name__)

    import asyncio
    try:
        text = asyncio.run(MockLLMProvider().generate("Explain", {"diagnosed_stage": "IDEATION", "blockers": []}))
        record("llm_mock_fallback", "Mock provider returns deterministic text", "Diagnostic summary" in text, text)
    except Exception as exc:
        record("llm_mock_fallback", "Mock provider returns deterministic text", False, repr(exc))

    from datetime import UTC, datetime, timedelta
    try:
        manager = DecryptionLeaseManager(default_ttl_minutes=120)
        now = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
        lease = manager.create_lease(subject_id="project-1", purpose="analysis", now=now)
        try:
            manager.validate(lease.lease_id, subject_id="project-1", purpose="analysis", now=now + timedelta(hours=2))
            record("expired_decryption_lease", "Expired lease is denied", False, "lease accepted")
        except LeaseExpired:
            record("expired_decryption_lease", "Expired lease is denied", True, "LeaseExpired")
    except Exception as exc:
        record("expired_decryption_lease", "Expired lease is denied", False, repr(exc))

    try:
        response = TestClient(gateway_app).get("/api/v1/projects")
        record("unauthorized_project_route", "Protected route returns 401/403", response.status_code in {401, 403}, str(response.status_code))
    except Exception as exc:
        record("unauthorized_project_route", "Protected route returns 401/403", False, repr(exc))

    passed = sum(1 for case in cases if case["pass"])
    return {
        "cases": cases,
        "no_crash_rate": passed / len(cases),
        "graceful_degradation_rate": passed / len(cases),
        "fallback_success_rate": passed / len(cases),
    }


def _security_metrics() -> dict[str, Any]:
    payload = {"sector": "private-medtech-sector", "monthly_revenue": 4200}
    encryptor = DataEncryptor(DataEncryptor.generate_key())
    envelope = encryptor.encrypt_json(payload, aad="project:demo")
    round_trip = encryptor.decrypt_json(envelope, aad="project:demo") == payload
    plaintext_absent = "private-medtech-sector" not in envelope.ciphertext
    return {
        "aes_gcm_round_trip_pass": round_trip,
        "plaintext_absent_from_ciphertext": plaintext_absent,
        "decryption_lease_ttl_minutes": 120,
    }


def _write_confusion_matrix(path: Path, matrix: dict[str, dict[str, int]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["actual\\predicted", *STAGES])
        for actual in STAGES:
            writer.writerow([actual, *[matrix[actual][pred] for pred in STAGES]])


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    profile_rows = _load_csv(SYNTHETIC_DIR / "entrepreneur_profiles.csv")
    scoring_rows = _load_csv(SYNTHETIC_DIR / "scoring_cases.csv")
    blocker_rows = _load_csv(SYNTHETIC_DIR / "blocker_labels.csv")
    profiles = [_profile_from_row(row) for row in profile_rows]
    predictor = RuleBasedMaturityPredictor()
    blocker_detector = RuleBasedBlockerDetector()

    y_true = [row["expected_stage"] for row in profile_rows]
    predictions = [predictor.predict(profile) for profile in profiles]
    y_pred = [str(pred.diagnosed_stage) for pred in predictions]
    maturity = _classification_metrics(y_true, y_pred, STAGES)
    high_ready = {"FUNDRAISING", "LAUNCH_PLANNING", "GROWTH"}
    high_risk_false_ready = [
        row["project_id"] for row, pred in zip(profile_rows, y_pred, strict=True)
        if pred in high_ready and row["expected_stage"] not in high_ready
    ]

    expected_blockers = [
        {label: _int(row[label]) for label in BLOCKER_LABELS}
        for row in blocker_rows
    ]
    actual_blockers = []
    blocker_case_rows = []
    for row, profile, prediction, expected in zip(profile_rows, profiles, predictions, expected_blockers, strict=True):
        result = blocker_detector.detect(profile, prediction)
        actual_types = {str(blocker.type) for blocker in result.blockers}
        actual = {label: int(label in actual_types) for label in BLOCKER_LABELS}
        actual_blockers.append(actual)
        for label in BLOCKER_LABELS:
            blocker_case_rows.append({
                "case_id": row["project_id"],
                "expected": label if expected[label] else "none",
                "actual": label if actual[label] else "none",
                "pass": bool(expected[label] == actual[label]),
            })
    blocker_metrics = _multilabel_metrics(expected_blockers, actual_blockers)

    cases = json.loads(EVAL_CASES.read_text(encoding="utf-8-sig"))
    score_metrics = _score_metrics(profiles, scoring_rows)
    anomaly_metrics = _anomaly_metrics()
    resource_metrics = _resource_metrics(cases)
    roadmap_metrics = _roadmap_metrics(profiles)
    robustness_metrics = _robustness_metrics()
    security_metrics = _security_metrics()

    measured = {
        "synthetic_evaluation_dataset": True,
        "dataset": {
            "profile_count": len(profiles),
            "blocker_label_count": len(blocker_rows),
            "scoring_hint_count": len(scoring_rows),
            "resource_query_count": len(cases["resource_queries"]),
            "source_files": [
                "data/synthetic/entrepreneur_profiles.csv",
                "data/synthetic/blocker_labels.csv",
                "data/synthetic/scoring_cases.csv",
                "data/evaluation/evaluation_cases.json",
            ],
        },
        "maturity": {
            **maturity,
            "high_risk_false_ready_count": len(high_risk_false_ready),
            "high_risk_false_ready_rate": len(high_risk_false_ready) / len(profiles),
            "high_risk_false_ready_case_ids": high_risk_false_ready[:20],
        },
        "blockers": blocker_metrics,
        "scoring": score_metrics,
        "anomalies": anomaly_metrics,
        "resources": resource_metrics,
        "roadmap": roadmap_metrics,
        "robustness": robustness_metrics,
        "security": security_metrics,
        "not_measured": {
            "shap_availability_rate": {
                "status": "Not measured in current MVP",
                "reason": "No executable SHAP or TreeExplainer integration is present; SklearnMaturityPredictor delegates to rule-based prediction.",
                "recommended_next_step": "Train/load a RandomForestClassifier and add a SHAP evaluation harness over a labelled validation set.",
            },
            "rag_vector_metrics": {
                "status": "Not measured in current MVP",
                "reason": "The runnable resource service uses metadata/lexical rule matching over local JSON; no vector retrieval or reranker endpoint is active.",
                "recommended_next_step": "Expose a vector retrieval service and add query-level relevance labels for Precision@K, Recall@K, MRR, and source grounding.",
            },
            "production_latency": {
                "status": "Not measured in current MVP",
                "reason": "Only local in-process benchmarks are generated; Docker/PostgreSQL/pgvector production-scale benchmarks are not run by this script.",
                "recommended_next_step": "Run the benchmark through Docker Compose with warm services and persisted logs.",
            },
            "counterfactual_action_impact": {
                "status": roadmap_metrics["counterfactual_status"],
                "reason": roadmap_metrics["counterfactual_reason"],
                "recommended_next_step": "Add stable fixtures for shared.domain.scoring_intelligence.MassarIntelligenceEngine and export counterfactual deltas.",
            },
        },
    }

    metrics_summary = {
        "maturity_accuracy": maturity["accuracy"],
        "maturity_macro_f1": maturity["macro_f1"],
        "high_risk_false_ready_rate": measured["maturity"]["high_risk_false_ready_rate"],
        "blocker_micro_f1": blocker_metrics["micro_f1"],
        "blocker_macro_f1": blocker_metrics["macro_f1"],
        "score_reproducibility_rate": score_metrics["reproducibility_rate"],
        "lambda_penalty_correctness_rate": score_metrics["lambda_penalty_correctness_rate"],
        "market_score_mae_against_synthetic_hint": score_metrics["market_score_mae_against_synthetic_hint"],
        "scalability_score_mae_against_synthetic_hint": score_metrics["scalability_score_mae_against_synthetic_hint"],
        "anomaly_detection_accuracy": anomaly_metrics["anomaly_detection_accuracy"],
        "anomaly_false_alert_rate": anomaly_metrics["false_alert_rate_on_clean_case"],
        "resource_precision_at_3": resource_metrics["precision_at_3"],
        "resource_recall_at_3": resource_metrics["recall_at_3"],
        "resource_mrr": resource_metrics["mrr"],
        "source_grounding_rate": resource_metrics["source_grounding_rate"],
        "eligibility_rule_accuracy": resource_metrics["eligibility_rule_accuracy"],
        "roadmap_grounding_rate": roadmap_metrics["roadmap_grounding_rate"],
        "robustness_no_crash_rate": robustness_metrics["no_crash_rate"],
        "security_encryption_round_trip_pass": security_metrics["aes_gcm_round_trip_pass"],
    }

    (ARTIFACT_DIR / "results.json").write_text(json.dumps(measured, indent=2, default=str), encoding="utf-8")
    (ARTIFACT_DIR / "metrics.json").write_text(json.dumps(metrics_summary, indent=2, default=str), encoding="utf-8")
    _write_confusion_matrix(ARTIFACT_DIR / "confusion_matrix.csv", maturity["confusion_matrix"])
    (ARTIFACT_DIR / "test_case_inventory.json").write_text(json.dumps({
        "maturity_profile_ids": [row["project_id"] for row in profile_rows],
        "resource_queries": cases["resource_queries"],
        "robustness_cases": robustness_metrics["cases"],
        "anomaly_cases": anomaly_metrics["cases"],
        "blocker_case_sample": blocker_case_rows[:50],
    }, indent=2, default=str), encoding="utf-8")
    print(json.dumps(metrics_summary, indent=2, default=str))


if __name__ == "__main__":
    main()
