from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from shared.application.fastapi import create_service_app
from shared.llm import MockLLMProvider

app = create_service_app("Explainability Service", "explainability_service")
provider = MockLLMProvider()


class ExplainPayload(BaseModel):
    prompt: str
    context: dict[str, Any]


@app.post("/explain")
async def explain(payload: ExplainPayload) -> dict[str, str]:
    text = await provider.generate(payload.prompt, payload.context)
    return {"short": text, "detailed": text}
