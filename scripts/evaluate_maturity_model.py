from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "evaluation" / "maturity_report.json"


def main() -> None:
    report = {
        "maturity_accuracy": 0.75,
        "maturity_macro_f1": 0.72,
        "blocker_micro_f1": 0.78,
        "blocker_macro_f1": 0.74,
        "score_consistency": 0.83,
        "retrieval_precision_at_3": 0.8,
        "eligibility_accuracy": 0.77,
        "roadmap_grounding_rate": 1.0,
        "average_latency": 0.0,
        "synthetic": True,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote evaluation report to {OUTPUT}")


if __name__ == "__main__":
    main()
