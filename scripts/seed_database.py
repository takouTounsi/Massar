from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_synthetic_profiles import main as generate_profiles  # noqa: E402


def main() -> None:
    generate_profiles()
    resources_path = ROOT / "data" / "knowledge_base" / "resources.json"
    resources = json.loads(resources_path.read_text(encoding="utf-8"))
    if len(resources) != 7:
        raise RuntimeError(f"Expected 7 synthetic resources, found {len(resources)}")
    if not all(resource.get("synthetic") is True for resource in resources):
        raise RuntimeError("All seed resources must be marked synthetic: true")
    print("Seed completed: 100 profiles and 7 synthetic resources are available.")


if __name__ == "__main__":
    main()
