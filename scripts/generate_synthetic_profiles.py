from __future__ import annotations

import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DIR = ROOT / "data" / "synthetic"
STAGES = ["IDEATION", "MARKET_VALIDATION", "STRUCTURATION", "FUNDRAISING", "LAUNCH_PLANNING", "GROWTH"]
COUNTRIES = ["TN", "MA", "DZ"]
SECTORS = ["technology", "agriculture", "construction", "retail", "industry", "services"]


def generate_profiles(count: int = 100, seed: int = 42) -> list[dict[str, object]]:
    random.seed(seed)
    profiles: list[dict[str, object]] = []
    for index in range(count):
        stage = STAGES[index % len(STAGES)]
        country = COUNTRIES[index % len(COUNTRIES)]
        business_type = "startup" if index % 2 == 0 else "traditional_business"
        paying_customers = {
            "IDEATION": 0,
            "MARKET_VALIDATION": random.choice([0, 1]),
            "STRUCTURATION": random.choice([0, 2]),
            "FUNDRAISING": random.choice([1, 3]),
            "LAUNCH_PLANNING": random.choice([2, 5]),
            "GROWTH": random.choice([6, 12, 25]),
        }[stage]
        declared_stage = random.choice(STAGES) if index % 7 == 0 else stage
        profiles.append(
            {
                "project_id": f"synthetic-profile-{index + 1:03d}",
                "country": country,
                "business_type": business_type,
                "sector": random.choice(SECTORS),
                "declared_stage": declared_stage,
                "expected_stage": stage,
                "primary_goal": "public_procurement" if index % 11 == 0 else random.choice(["funding", "growth", "launch", "export"]),
                "has_mvp": stage != "IDEATION",
                "has_revenue": paying_customers > 0,
                "paying_customers": paying_customers,
                "documented_interviews": random.choice([0, 3, 8, 15, 25]),
                "process_automation_level": round(random.random(), 2),
                "wants_public_tenders": index % 11 == 0,
                "administrative_documents_ready": index % 5 == 0,
                "financial_capacity_score": random.randint(15, 90),
                "synthetic": True,
            }
        )
    return profiles


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    profiles = generate_profiles()
    write_csv(SYNTHETIC_DIR / "entrepreneur_profiles.csv", profiles)
    write_csv(
        SYNTHETIC_DIR / "scoring_cases.csv",
        [
            {
                "case_id": row["project_id"],
                "country": row["country"],
                "expected_stage": row["expected_stage"],
                "market_score_hint": 35 + int(row["paying_customers"]) * 5,
                "scalability_score_hint": int(float(row["process_automation_level"]) * 100),
                "synthetic": True,
            }
            for row in profiles
        ],
    )
    write_csv(
        SYNTHETIC_DIR / "blocker_labels.csv",
        [
            {
                "case_id": row["project_id"],
                "MARKET_VALIDATION_BLOCKER": int(int(row["paying_customers"]) == 0),
                "TENDER_READINESS_BLOCKER": int(bool(row["wants_public_tenders"]) and not bool(row["administrative_documents_ready"])),
                "SCALABILITY_BLOCKER": int(float(row["process_automation_level"]) < 0.35 and row["expected_stage"] == "GROWTH"),
                "synthetic": True,
            }
            for row in profiles
        ],
    )
    write_csv(
        SYNTHETIC_DIR / "tender_readiness_cases.csv",
        [
            {
                "case_id": row["project_id"],
                "country": row["country"],
                "wants_public_tenders": row["wants_public_tenders"],
                "administrative_documents_ready": row["administrative_documents_ready"],
                "financial_capacity_score": row["financial_capacity_score"],
                "expected_status": "READY" if bool(row["administrative_documents_ready"]) and int(row["financial_capacity_score"]) > 60 else "NOT_READY",
                "synthetic": True,
            }
            for row in profiles
            if bool(row["wants_public_tenders"])
        ],
    )
    print(f"Generated {len(profiles)} synthetic profiles in {SYNTHETIC_DIR}")


if __name__ == "__main__":
    main()
