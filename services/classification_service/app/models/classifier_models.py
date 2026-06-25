from __future__ import annotations

from pydantic import BaseModel
from typing import List

from shared.contracts.schemas import StartupTranscriptEntry


class ClassificationSession(BaseModel):
    session_id: str
    industry_key: str
    transcript: List[StartupTranscriptEntry] = []


class ClassificationResult(BaseModel):
    session_id: str
    node_id: str
    is_terminal: bool
    payload: dict
