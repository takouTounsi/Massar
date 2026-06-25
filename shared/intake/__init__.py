"""Adaptive Intake Engine for MASSAR.

Owns the dynamic questionnaire, evidence extraction, the evidence ledger, probe
firing and next-question selection. It never assigns a maturity stage or a score
and never lets the LLM make a verdict — those are downstream consumers that read
the shared profile + evidence ledger. See docs/intake-engine.md.
"""

from __future__ import annotations

import logging

from shared.config import get_settings
from shared.intake.contracts import (
    AnswerResponse,
    ExtractionResult,
    IntakeState,
    LedgerEntry,
    SessionStartResponse,
    StateResponse,
)
from shared.intake.engine import IntakeEngine
from shared.intake.extractor import Extractor
from shared.intake.pml_adapter import AdaptedPML, adapt_pml
from shared.intake.profile_writer import (
    InMemoryProfileWriter,
    PostgresProfileWriter,
    ProfileWriter,
)
from shared.intake.session_manager import (
    InMemorySessionStore,
    SessionStore,
    build_session_store,
)
from shared.llm import MockLLMProvider, OpenAICompatibleProvider

logger = logging.getLogger("intake.extractor")

# Provider identifiers that map to the OpenAI-compatible HTTP client (OpenRouter,
# vLLM, LocalAI, OpenAI itself, ...). They all speak /chat/completions.
_OPENAI_COMPATIBLE_PROVIDERS = {"openai_compatible", "openrouter", "openai", "vllm"}

__all__ = [
    "AdaptedPML",
    "AnswerResponse",
    "ExtractionResult",
    "Extractor",
    "InMemoryProfileWriter",
    "InMemorySessionStore",
    "IntakeEngine",
    "IntakeState",
    "LedgerEntry",
    "PostgresProfileWriter",
    "ProfileWriter",
    "SessionStartResponse",
    "SessionStore",
    "StateResponse",
    "adapt_pml",
    "build_extractor",
    "build_session_store",
]


def build_extractor() -> Extractor:
    """Build the extractor's LLM provider from settings.

    Any OpenAI-compatible provider (``openai_compatible``, ``openrouter``, ...) with
    a base URL configured uses the real HTTP client; otherwise we fall back to the
    mock provider and log a loud WARNING, because the mock returns prose — every
    field then degrades to MISSING and the engine silently behaves like a linear
    form (see R1). The warning makes that degraded state visible at startup.
    """

    settings = get_settings()
    provider_id = (settings.llm_provider or "mock").lower()
    if provider_id in _OPENAI_COMPATIBLE_PROVIDERS and settings.openai_compatible_base_url:
        logger.info(
            "intake extractor using OpenAI-compatible provider=%s base_url=%s model=%s",
            provider_id,
            settings.openai_compatible_base_url,
            settings.openai_compatible_model or "gpt-4o-mini",
        )
        provider: object = OpenAICompatibleProvider(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key or "",
            model=settings.openai_compatible_model or "gpt-4o-mini",
        )
    else:
        logger.warning(
            "intake extractor falling back to MockLLMProvider (llm_provider=%r, "
            "base_url=%r): extraction will DEGRADE to all-MISSING and adaptive "
            "branching (probes/contradictions/skips) will NOT fire. Configure "
            "LLM_PROVIDER=openrouter + OPENAI_COMPATIBLE_BASE_URL for the real path.",
            settings.llm_provider,
            settings.openai_compatible_base_url,
        )
        provider = MockLLMProvider()
    return Extractor(provider)  # type: ignore[arg-type]
