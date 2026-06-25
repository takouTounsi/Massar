"""The ONLY LLM call in the engine.

The extractor turns free AR/FR text into structured fields. It is handed a schema
*scoped to the current question's fields only* (hard invariant #2), so the model
cannot invent fields. It never selects questions, assigns a stage, or scores
(hard invariant #1). It returns per-field ``CONFIRMED | UNVERIFIED | MISSING``;
``CONTRADICTED`` is decided later by the contradiction detector.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from shared.contracts.enums import EvidenceStatus
from shared.intake.contracts import ExtractionResult, FieldSpec, IntakeQuestion
from shared.intake.question_bank import QUESTIONS
from shared.intake.requirements import REQUIREMENTS

logger = logging.getLogger("intake.extractor")

# Fields the engine recognises for *unprompted* (volunteered) signals. The
# scoped ``extracted`` channel is restricted to the current question's fields;
# anything else volunteered must still be a known field to be recorded.
KNOWN_FIELDS: set[str] = set(REQUIREMENTS) | {
    spec.name for question in QUESTIONS for spec in question.extract_fields
}

# PII redaction applied to *stored* answers (extraction still sees the original).
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+?216[\s-]?)?\d{2}[\s.-]?\d{3}[\s.-]?\d{3}\b")
_LONG_ID_RE = re.compile(r"\b\d{7,}\b")  # tax IDs / RNE / matricule fiscal


def redact_pii(text: str) -> str:
    """Mask emails, phone numbers and long identifiers before persistence."""

    text = _EMAIL_RE.sub("[email]", text)
    text = _PHONE_RE.sub("[phone]", text)
    text = _LONG_ID_RE.sub("[id]", text)
    return text


def _parse_json(text: object) -> dict[str, Any] | None:
    """Tolerantly extract a JSON object from possibly fenced/prose-wrapped text."""

    if not isinstance(text, str):
        return None
    candidate = text.strip()
    # Strip ```json ... ``` / ``` ... ``` fences.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    # Fall back to the first balanced {...} span.
    start = candidate.find("{")
    if start == -1:
        return None
    depth = 0
    for index in range(start, len(candidate)):
        char = candidate[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(candidate[start : index + 1])
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


class ExtractionLLM(Protocol):
    async def generate(self, prompt: str, context: dict[str, Any]) -> str: ...


def _coerce(value: Any, spec: FieldSpec) -> Any:
    if value is None:
        return None
    try:
        if spec.type == "boolean":
            if isinstance(value, str):
                return value.strip().lower() in {"true", "oui", "yes", "نعم", "1"}
            return bool(value)
        if spec.type == "integer":
            return int(value)
        if spec.type == "number":
            return float(value)
        if spec.type == "enum" and spec.options and value not in spec.options:
            return None
    except (TypeError, ValueError):
        return None
    return value


def build_prompt(question: IntakeQuestion, raw_answer: str, lang: str) -> str:
    """Render the scoped extraction instruction for the LLM."""

    schema_lines = []
    for spec in question.extract_fields:
        hint = spec.description.get(lang) or spec.description.get("fr") or ""
        opts = f" options={spec.options}" if spec.options else ""
        schema_lines.append(f'  - "{spec.name}" ({spec.type}){opts}: {hint}')
    schema = "\n".join(schema_lines)
    allowed = ", ".join(f'"{spec.name}"' for spec in question.extract_fields)
    return (
        "You are a structured-data extractor for a Tunisian entrepreneurship intake.\n"
        "Extract ONLY the following fields from the answer. Do not invent fields, "
        "do not infer a maturity stage, do not score.\n"
        f"FIELDS (the only allowed keys in `extracted`): {allowed}\n"
        f"{schema}\n"
        "Return STRICT JSON:\n"
        '{"extracted": {"<field>": {"value": <value|null>, '
        '"status": "CONFIRMED|UNVERIFIED|MISSING"}}, '
        '"unprompted_signals": {"<other_field>": <value>}}\n'
        "Rules: status=CONFIRMED only when the answer states it clearly; "
        "UNVERIFIED when implied/claimed without proof; MISSING when absent or "
        '"je ne sais pas"/"لا أعرف". The text may mix Arabic and French.\n'
        f"ANSWER:\n{raw_answer}"
    )


class Extractor:
    def __init__(self, provider: ExtractionLLM, max_attempts: int = 2) -> None:
        self._provider = provider
        self._max_attempts = max(1, max_attempts)

    async def extract(
        self, question: IntakeQuestion, raw_answer: str, lang: str = "fr"
    ) -> ExtractionResult:
        prompt = build_prompt(question, raw_answer, lang)
        context = {"question_id": question.id, "json_mode": True}

        provider_name = type(self._provider).__name__
        payload: dict[str, Any] | None = None
        for attempt in range(self._max_attempts):
            try:
                raw = await self._provider.generate(prompt, context)
            except Exception as exc:  # noqa: BLE001 - any provider/network error degrades the turn
                logger.warning(
                    "extraction provider=%s question=%s attempt=%d raised %s: %s",
                    provider_name, question.id, attempt + 1, type(exc).__name__, exc,
                )
                continue
            payload = _parse_json(raw)
            if payload is not None:
                break
            logger.warning(
                "extraction provider=%s question=%s attempt=%d returned unparseable "
                "(non-JSON) output: %r",
                provider_name, question.id, attempt + 1, str(raw)[:120],
            )

        degraded = payload is None
        if degraded:
            logger.warning(
                "extraction DEGRADED to all-MISSING for question=%s using provider=%s "
                "(%s). If this is MockLLMProvider the engine is running the degraded "
                "linear-form fallback — configure a real LLM_PROVIDER.",
                question.id, provider_name,
                "mock returns prose, not JSON" if provider_name == "MockLLMProvider"
                else "no parseable JSON after retries",
            )
        payload = payload or {}

        scoped = {spec.name: spec for spec in question.extract_fields}
        extracted: dict[str, Any] = {}
        evidence_status: dict[str, EvidenceStatus] = {}

        raw_extracted = payload.get("extracted", {}) if isinstance(payload, dict) else {}
        for name, spec in scoped.items():
            cell = raw_extracted.get(name) if isinstance(raw_extracted, dict) else None
            if not isinstance(cell, dict):
                evidence_status[name] = EvidenceStatus.MISSING
                continue
            value = _coerce(cell.get("value"), spec)
            try:
                status = EvidenceStatus(cell.get("status", "MISSING"))
            except ValueError:
                status = EvidenceStatus.MISSING
            if value is None:
                status = EvidenceStatus.MISSING
            if status is not EvidenceStatus.MISSING:
                extracted[name] = value
            evidence_status[name] = status

        # Unprompted signals: volunteered, must be known fields, never in scope.
        raw_signals = payload.get("unprompted_signals", {}) if isinstance(payload, dict) else {}
        unprompted: dict[str, Any] = {}
        if isinstance(raw_signals, dict):
            for name, value in raw_signals.items():
                if name in scoped or name not in KNOWN_FIELDS or value is None:
                    continue
                unprompted[name] = value

        return ExtractionResult(
            extracted=extracted,
            evidence_status=evidence_status,
            unprompted_signals=unprompted,
            degraded=degraded,
        )
