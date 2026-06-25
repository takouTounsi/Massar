from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    event_type: str
    project_id: UUID
    service: str
    action: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model_version: str | None = None
    rule_version: str | None = None
    input_hash: str
    output_summary: dict[str, Any]
    correlation_id: str


def _hash_payload(payload: dict[str, Any]) -> str:
    content = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_audit_event(
    *,
    event_type: str,
    project_id: UUID,
    service: str,
    action: str,
    input_payload: dict[str, Any],
    output_summary: dict[str, Any],
    correlation_id: str,
    model_version: str | None = None,
    rule_version: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_type=event_type,
        project_id=project_id,
        service=service,
        action=action,
        model_version=model_version,
        rule_version=rule_version,
        input_hash=_hash_payload(input_payload),
        output_summary=output_summary,
        correlation_id=correlation_id,
    )
