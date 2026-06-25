from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Callable, Any
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.application import InMemoryOrientationPipeline
from shared.contracts.enums import BusinessType, CountryCode, MaturityStage
from shared.contracts.schemas import ProjectCreateRequest, ProjectProfile
from shared.domain.blockers import RuleBasedBlockerDetector
from shared.domain.eligibility import evaluate_eligibility
from shared.domain.maturity import RuleBasedMaturityPredictor
from shared.domain.resources import match_resources
from shared.domain.scoring import WeightedRuleScoreCalculator

ARTIFACT_DIR = ROOT / "artifacts" / "evaluation"
SYNTHETIC = ROOT / "data" / "synthetic" / "entrepreneur_profiles.csv"


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _rows() -> list[dict[str, str]]:
    with SYNTHETIC.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _profile(row: dict[str, str]) -> ProjectProfile:
    paying = int(float(row["paying_customers"]))
    automation = float(row["process_automation_level"])
    return ProjectProfile(
        project_id=uuid5(NAMESPACE_URL, row["project_id"]),
        country=CountryCode(row["country"]),
        business_type=BusinessType(row["business_type"]),
        sector=row["sector"],
        declared_stage=MaturityStage(row["declared_stage"]),
        primary_goal=row["primary_goal"],
        has_mvp=_bool(row["has_mvp"]),
        has_revenue=_bool(row["has_revenue"]),
        monthly_revenue=paying * 500.0,
        paying_customers=paying,
        documented_interviews=int(float(row["documented_interviews"])),
        process_automation_level=automation,
        wants_public_tenders=_bool(row["wants_public_tenders"]),
        administrative_documents_ready=_bool(row["administrative_documents_ready"]),
        financial_capacity_score=int(float(row["financial_capacity_score"])),
        market_size_known=int(float(row["documented_interviews"])) >= 15,
        competition_understanding=55,
        revenue_model_clarity=70 if paying else 35,
        team_size=3,
        tech_stack_scalability=int(automation * 100),
        infrastructure_readiness=int(automation * 100),
        problem_novelty_score=60,
        technology_readiness_level=5 if _bool(row["has_mvp"]) else 2,
        process_documentation_score=int(automation * 100),
        financial_model_quality=int(float(row["financial_capacity_score"])),
        legal_compliance_score=80 if _bool(row["administrative_documents_ready"]) else 35,
    )


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def _bench(name: str, runs: int, fn: Callable[[], None]) -> dict[str, Any]:
    durations: list[float] = []
    errors = 0
    for _ in range(runs):
        start = time.perf_counter()
        try:
            fn()
        except Exception:
            errors += 1
        durations.append((time.perf_counter() - start) * 1000.0)
    return {
        "operation": name,
        "environment": "local in-process Python on developer workstation",
        "runs": runs,
        "p50_ms": round(statistics.median(durations), 3),
        "p95_ms": round(_percentile(durations, 95), 3),
        "min_ms": round(min(durations), 3),
        "max_ms": round(max(durations), 3),
        "error_rate": errors / runs,
        "llm_enabled": False,
        "data_source": "local CSV/JSON and in-memory services",
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    profiles = [_profile(row) for row in _rows()[:30]]
    scoring = WeightedRuleScoreCalculator()
    maturity_predictor = RuleBasedMaturityPredictor()
    blockers = RuleBasedBlockerDetector()

    score_index = 0
    def score_once() -> None:
        nonlocal score_index
        scoring.calculate(profiles[score_index % len(profiles)])
        score_index += 1

    resource_index = 0
    def resources_once() -> None:
        nonlocal resource_index
        profile = profiles[resource_index % len(profiles)]
        maturity = maturity_predictor.predict(profile)
        scores = scoring.calculate(profile)
        blocker_result = blockers.detect(profile, maturity)
        match_resources(profile, maturity, scores, blocker_result)
        resource_index += 1

    analysis_index = 0
    def analysis_once() -> None:
        nonlocal analysis_index
        row = _rows()[analysis_index % 30]
        pipeline = InMemoryOrientationPipeline()
        project = pipeline.create_project(ProjectCreateRequest(
            country=row["country"],
            business_type=row["business_type"],
            sector=row["sector"],
            declared_stage=row["declared_stage"],
            primary_goal=row["primary_goal"],
        ))
        pipeline.update_project(project.project_id, profiles[analysis_index % len(profiles)].model_dump(exclude={"project_id", "created_at", "updated_at", "history", "version"}))
        pipeline.run_analysis(project.project_id)
        analysis_index += 1

    results = {
        "benchmark_metadata": {
            "synthetic_evaluation_dataset": True,
            "profile_sample_size": len(profiles),
            "note": "Local in-process benchmark. This is not a Docker/PostgreSQL/pgvector production benchmark.",
        },
        "operations": [
            _bench("Score calculation", 30, score_once),
            _bench("Resource matching", 30, resources_once),
            _bench("Full in-memory analysis", 20, analysis_once),
        ],
    }
    (ARTIFACT_DIR / "latency_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
