from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from shared.application.fastapi import create_service_app
from shared.llm import MockLLMProvider

app = create_service_app("Assistant Service", "assistant_service")
provider = MockLLMProvider()


class AssistantPayload(BaseModel):
    message: str
    context: dict[str, Any] = {}


@app.post("/assistant")
async def assistant(payload: AssistantPayload) -> dict[str, str]:
    text = await provider.generate(payload.message, payload.context)
    return {"answer": text}
