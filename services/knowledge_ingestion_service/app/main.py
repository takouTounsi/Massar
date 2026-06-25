from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from shared.application.fastapi import create_service_app
from shared.embeddings import LocalHashEmbeddingProvider

app = create_service_app("Knowledge Ingestion Service", "knowledge_ingestion_service")
embedding_provider = LocalHashEmbeddingProvider()


class IngestPayload(BaseModel):
    path: str = "data/knowledge_base/resources.json"


@app.post("/knowledge/ingest")
async def ingest(payload: IngestPayload) -> dict[str, int | str]:
    path = Path(payload.path)
    if not path.exists():
        return {"status": "missing", "chunks": 0}
    vector = embedding_provider.embed(path.read_text(encoding="utf-8")[:1000])
    return {"status": "ok", "chunks": 1, "embedding_dimensions": len(vector)}
