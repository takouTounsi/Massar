from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "models" / "maturity" / "sklearn-v0.1.0.metadata.json"


def main() -> None:
    OUTPUT.write_text(
        json.dumps(
            {
                "name": "sklearn_maturity",
                "version": "sklearn-v0.1.0",
                "status": "placeholder_trained_from_synthetic_seed",
                "fallback": "rules-v0.1.0",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote model metadata to {OUTPUT}")


if __name__ == "__main__":
    main()
