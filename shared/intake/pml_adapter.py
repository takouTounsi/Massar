"""Boundary adapter: Classification Service PML payload -> our isolated declared_stage.

The Classification Service (``services/classification_service``) exposes a
"Perceived Maturity Level" (PML) classifier. Its terminal payload carries a
``phase`` drawn from a *generic* product-maturity ladder
(IDEATION / POC_MVP / PMF / SCALE / GROWTH). That phase is the founder's
**self-assessment** — in our design it is ``declared_stage`` (§9.6): an OPINION to
be verified, never evidence.

This module is the **only** place their vocabulary and DTO shape are known.
It converts their phase into OUR ``EvidenceStage`` representation (the same
``"S1".."S6"`` string our inline ``q_declared_stage`` produces, which
``_declared_to_maturity`` already understands) and keeps their transcript as an
opaque blob. Nothing of theirs leaks past this boundary: their phase strings,
field names, and transcript shape stay here; callers receive an ``AdaptedPML``.

Invariants this adapter enforces (do not relax):

* **Declared-side only.** PML flows ONLY to the perception/gap layer. This module
  never touches the ``evidence_ledger``, the stage gates, missing-info, or
  question selection. We verify the opinion; we do not trust it.
* **Transcript is reference context only.** It NEVER auto-populates CONFIRMED
  ledger fields. A claim in their transcript is UNVERIFIED until our extractor +
  gates confirm it.
* **Never crash, never guess silently.** Missing/extra fields and unrecognized
  phases are handled defensively; PML is optional (the engine runs without it,
  the gap is simply not computed). Conservative/approximate mappings are logged.

Phase -> stage mapping (5 generic phases -> our 6 document-gated S-stages). The
mapping is conservative: a phase that straddles two of our stages maps to the
*lower* one so PML never inflates the founder's declared side. Two consequences
are inherent and accepted: our **S2** (problem-validated, informal) is
unreachable from PML, and the top (their SCALE/GROWTH) compresses onto S5/S6 —
both are fine because this is only the *declared* side; the evidence path can
still diagnose S2 etc.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from shared.contracts.enums import EvidenceStage

logger = logging.getLogger("intake.pml_adapter")

# Their phase vocabulary -> our document-gated S-stage. See module docstring.
_PHASE_TO_EVIDENCE_STAGE: dict[str, EvidenceStage] = {
    "IDEATION": EvidenceStage.S1,
    "POC_MVP": EvidenceStage.S3,
    "PMF": EvidenceStage.S4,
    "SCALE": EvidenceStage.S5,
    "GROWTH": EvidenceStage.S6,
}

# Phases that straddle our taxonomy and are mapped conservatively (downward):
# IDEATION could be our S1 or S2; SCALE could be our S5 or S6. Logged, never silent.
_APPROXIMATED_PHASES: frozenset[str] = frozenset({"IDEATION", "SCALE"})


@dataclass(frozen=True)
class AdaptedPML:
    """Our internal view of a PML payload. The only type that crosses the boundary.

    ``transcript`` is opaque reference context: callers may store/show it but must
    NEVER feed it to the extractor or write it into the evidence ledger.
    """

    declared_stage: str | None  # "S1".."S6" or None when no usable PML
    raw_phase: str | None  # their original phase string, kept for traceability
    transcript: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    approximated: bool = False  # True when mapped conservatively across a straddle
    recognized: bool = False  # False -> no declared_stage derivable; gap not computed


def _opaque_transcript(payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Copy their transcript into a plain, opaque tuple. We never interpret it."""

    raw = payload.get("transcript")
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(dict(entry) for entry in raw if isinstance(entry, Mapping))


def adapt_pml(payload: Mapping[str, Any] | None) -> AdaptedPML:
    """Convert a Classification Service terminal payload to our declared representation.

    Defensive by contract: ``None``, a non-mapping, a missing ``phase``, or an
    unrecognized phase all yield an ``unrecognized`` result (``declared_stage`` is
    ``None``) rather than raising — PML is optional and the engine must run without
    it. Never raises on the partner's payload.
    """

    if not isinstance(payload, Mapping):
        return AdaptedPML(declared_stage=None, raw_phase=None)

    transcript = _opaque_transcript(payload)
    raw_phase = payload.get("phase")

    if not isinstance(raw_phase, str) or not raw_phase.strip():
        logger.info("pml_no_phase: payload carried no usable phase; declared_stage not set")
        return AdaptedPML(declared_stage=None, raw_phase=None, transcript=transcript)

    stage = _PHASE_TO_EVIDENCE_STAGE.get(raw_phase.strip().upper())
    if stage is None:
        # An unknown phase (their taxonomy changed, or "UNKNOWN_PHASE" fallback).
        # Map to nothing rather than guess — the gap is simply not computed.
        logger.warning(
            "pml_unrecognized_phase: phase=%r has no stage mapping; declared_stage not set",
            raw_phase,
        )
        return AdaptedPML(declared_stage=None, raw_phase=raw_phase, transcript=transcript)

    approximated = raw_phase.strip().upper() in _APPROXIMATED_PHASES
    if approximated:
        logger.info(
            "pml_phase_approximated: phase=%s mapped conservatively to %s "
            "(straddles our taxonomy)",
            raw_phase.strip().upper(),
            stage.value,
        )

    return AdaptedPML(
        declared_stage=stage.value,
        raw_phase=raw_phase,
        transcript=transcript,
        approximated=approximated,
        recognized=True,
    )
