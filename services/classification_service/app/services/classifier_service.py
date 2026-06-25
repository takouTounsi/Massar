"""Service layer for classification operations.

Exposes helpers used by HTTP handlers or by other services (e.g. Intake Engine)
to persist perceived states and fetch results.
"""
from __future__ import annotations

from typing import Dict, Any

from os import environ

# Select repository implementation: prefer SQLAlchemy if configured, otherwise use in-memory repo.
if environ.get("CLASSIFIER_DB_URL"):
    from services.classification_service.app.repositories.sqlalchemy_repo import (
        init_db,
        save_session,
        save_result,
        get_session,
    )
    # initialize DB immediately using configured URL so tests and startup
    # that import this module don't forget to call init_db explicitly.
    try:
        init_db(environ.get("CLASSIFIER_DB_URL"))
    except Exception:
        # avoid crashing import (tests may still override or mock); errors
        # will surface when repo functions are called
        pass
else:
    from services.classification_service.app.repositories.classifier_repo import (
        save_session,
        save_result,
        get_session,
    )


def create_session(session_id: str, industry_key: str, metadata: Dict[str, Any] | None = None) -> None:
    session = {"session_id": session_id, "industry_key": industry_key, "metadata": metadata or {}, "results": []}
    save_session(session_id, session)


def persist_classification(session_id: str, node_id: str, is_terminal: bool, payload: Dict[str, Any]) -> None:
    result = {"node_id": node_id, "is_terminal": is_terminal, "payload": payload}
    save_result(session_id, result)


def fetch_session(session_id: str) -> Dict[str, Any] | None:
    return get_session(session_id)
