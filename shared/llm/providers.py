from __future__ import annotations

from typing import Any, Protocol

import httpx


class LLMProvider(Protocol):
    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        ...


class MockLLMProvider:
    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        stage = context.get("diagnosed_stage", "UNKNOWN")
        blockers = context.get("blockers", [])
        return f"Diagnostic summary: stage={stage}; blockers={len(blockers)}; prompt={prompt[:60]}"


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str, context: dict[str, Any]) -> str:
        json_mode = bool(context.get("json_mode"))
        system = (
            "Return only a single valid JSON object. No prose, no markdown."
            if json_mode
            else "Explain only from provided structured evidence. Do not invent facts."
        )
        # In json_mode the prompt is self-contained; do not leak the raw context dict.
        user = prompt if json_mode else f"{prompt}\nContext: {context}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"]["content"])
