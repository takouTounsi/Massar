"""A minimal SQLAlchemy-backed repository for classifier sessions/results.

This is intentionally small: it provides init_db(url) and the same
interface as the in-memory repo used in dev.
"""
from __future__ import annotations

from typing import Dict, Any
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    JSON,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine

_engine: Engine | None = None
_meta = MetaData()

sessions_table = Table(
    "classifier_sessions",
    _meta,
    Column("session_id", String, primary_key=True),
    Column("industry_key", String, nullable=False),
    Column("payload", JSON, nullable=False),
)


def init_db(database_url: str) -> None:
    global _engine
    _engine = create_engine(database_url)
    _meta.create_all(_engine)


def save_session(session_id: str, session_data: Dict[str, Any]) -> None:
    assert _engine is not None, "SQLAlchemy engine not initialized; call init_db(url)"
    with _engine.connect() as conn:
        conn.execute(
            sessions_table.insert().values(
                session_id=session_id, industry_key=session_data.get("industry_key", ""), payload=session_data
            )
        )
        conn.commit()


def get_session(session_id: str) -> Dict[str, Any] | None:
    if _engine is None:
        return None
    with _engine.connect() as conn:
        row = conn.execute(select(sessions_table).where(sessions_table.c.session_id == session_id)).first()
        if not row:
            return None
        return dict(row.payload)


def save_result(session_id: str, result: Dict[str, Any]) -> None:
    # For this minimal implementation we append result to payload.results in-place
    sess = get_session(session_id)
    if sess is None:
        raise KeyError("session not found")
    results = sess.get("results", [])
    results.append(result)
    sess["results"] = results
    # overwrite row
    with _engine.connect() as conn:
        conn.execute(
            sessions_table.update().where(sessions_table.c.session_id == session_id).values(payload=sess)
        )
        conn.commit()


def list_sessions() -> Dict[str, Dict[str, Any]]:
    if _engine is None:
        return {}
    with _engine.connect() as conn:
        rows = conn.execute(select(sessions_table)).fetchall()
        return {r.session_id: dict(r.payload) for r in rows}
