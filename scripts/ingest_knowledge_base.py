from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.embeddings import LocalHashEmbeddingProvider  # noqa: E402

SOURCE = ROOT / "data" / "knowledge_base" / "resources.json"
OUTPUT = ROOT / "data" / "processed" / "resource_chunks.json"


def main() -> None:
    resources = json.loads(SOURCE.read_text(encoding="utf-8"))
    embedder = LocalHashEmbeddingProvider()
    chunks = []
    for resource in resources:
        content = " ".join(
            [
                resource["name"],
                resource["institution"],
                resource["resource_type"],
                " ".join(resource.get("benefits", [])),
            ]
        )
        chunks.append(
            {
                "chunk_id": resource.get("source_chunk_ids", [f"{resource['id']}-chunk-001"])[0],
                "resource_id": resource["id"],
                "content": content,
                "metadata": {
                    "country": resource["country"],
                    "synthetic": resource["synthetic"],
                    "eligible_stages": resource["eligible_stages"],
                },
                "embedding": embedder.embed(content),
            }
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
    print(f"Ingested {len(chunks)} chunks into {OUTPUT}")


if __name__ == "__main__":
    main()
