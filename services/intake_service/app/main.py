from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel

from shared.application.fastapi import create_service_app
from shared.config import get_settings
from shared.contracts.schemas import IntakeAnswerResponse, IntakeSession, ProjectProfile
from shared.database.session import get_session_factory
from shared.domain.diagnosis import build_diagnosis
from shared.domain.intake import AdaptiveIntakeEngine
from shared.intake import (
    AnswerResponse,
    IntakeEngine,
    PostgresProfileWriter,
    SessionStartResponse,
    StateResponse,
    build_extractor,
    build_session_store,
)
from shared.intake.contracts import DiagnosisResponse
from shared.intake.missing_info import frontier_progress

app = create_service_app("Adaptive Intake Service", "intake_service")

# --- Legacy linear intake (kept intact; used by the gateway/orientation pipeline) ---
engine = AdaptiveIntakeEngine()
sessions: dict[UUID, IntakeSession] = {}

# classification endpoints should be hosted in the dedicated classification service.
# The mirrored copy was removed to avoid duplication; intake_service no longer mounts it.


class AnswerEnvelope(BaseModel):
    profile: ProjectProfile
    session: IntakeSession
    question_code: str
    value: object


@app.post("/intake/start", response_model=IntakeSession)
async def start_intake(profile: ProjectProfile) -> IntakeSession:
    session = engine.start(profile)
    sessions[session.session_id] = session
    return session


@app.post("/intake/answer", response_model=IntakeAnswerResponse)
async def answer_intake(payload: AnswerEnvelope) -> IntakeAnswerResponse:
    response = engine.answer(payload.profile, payload.session, payload.question_code, payload.value)
    sessions[response.session.session_id] = response.session
    return response


# --- Adaptive Intake Engine (evidence-ledger driven) ---
_settings = get_settings()


def _build_engine() -> IntakeEngine:
    writer = None
    if _settings.app_env != "local":
        try:
            writer = PostgresProfileWriter(get_session_factory())
        except Exception:  # pragma: no cover - DB optional
            writer = None
    return IntakeEngine(
        extractor=build_extractor(),
        session_store=build_session_store(_settings.redis_url),
        profile_writer=writer,
    )


adaptive_engine = _build_engine()


class StartRequest(BaseModel):
    project_id: UUID | None = None
    lang: str = "fr"


class AnswerRequest(BaseModel):
    raw_answer: str
    question_id: str


@app.post("/sessions", response_model=SessionStartResponse)
async def create_session(payload: StartRequest) -> SessionStartResponse:
    state = adaptive_engine.start_session(project_id=payload.project_id, lang=payload.lang)
    from shared.intake.question_bank import QUESTIONS_BY_ID

    question = QUESTIONS_BY_ID.get(state.current_question_id or "")
    return SessionStartResponse(
        session_id=state.session_id,
        first_question=question.render(state.lang) if question else None,
    )


@app.post("/sessions/{session_id}/answers", response_model=AnswerResponse)
async def submit_answer(session_id: UUID, payload: AnswerRequest) -> AnswerResponse:
    state = await adaptive_engine.process_answer(
        session_id, payload.raw_answer, payload.question_id
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown intake session")
    return _answer_response(state)


@app.post("/sessions/{session_id}/pml", response_model=StateResponse)
async def apply_pml(session_id: UUID, payload: dict) -> StateResponse:
    """Feed the Classification Service's PML payload into the declared/gap side.

    The raw partner payload is mapped at the boundary (``adapt_pml``) and written
    ONLY to ``declared_stage`` (the perception/gap side). It never enters the
    evidence ledger, gates, missing-info, or question selection, and is
    authoritative over our inline self-assessment question (§9.6 isolation).
    """

    state = adaptive_engine.apply_pml(session_id, payload)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown intake session")
    progress = frontier_progress(state)
    return StateResponse(
        phase=state.phase,
        frontier_stage=progress.frontier_stage,
        next_stage=progress.next_stage,
        gates_satisfied=progress.gates_satisfied,
        gates_total=progress.gates_total,
        percent_to_next=progress.percent_to_next,
        declared_stage=state.declared_stage,
        completed=state.completed,
    )


@app.get("/sessions/{session_id}/state", response_model=StateResponse)
async def session_state(session_id: UUID) -> StateResponse:
    state = adaptive_engine.get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown intake session")
    progress = frontier_progress(state)
    return StateResponse(
        phase=state.phase,
        frontier_stage=progress.frontier_stage,
        next_stage=progress.next_stage,
        gates_satisfied=progress.gates_satisfied,
        gates_total=progress.gates_total,
        percent_to_next=progress.percent_to_next,
        declared_stage=state.declared_stage,
        completed=state.completed,
    )


@app.get("/sessions/{session_id}/diagnosis", response_model=DiagnosisResponse)
async def session_diagnosis(session_id: UUID) -> DiagnosisResponse:
    """Run the downstream maturity predictor + scorer on the session's ledger (R2).

    Reuses the existing, unit-tested predictor/scorer via ``build_diagnosis``; the
    intake engine itself never assigns a stage (§9.1).
    """

    state = adaptive_engine.get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown intake session")
    return build_diagnosis(state)


@app.post("/sessions/{session_id}/resume", response_model=AnswerResponse)
async def resume_session(session_id: UUID) -> AnswerResponse:
    state = adaptive_engine.resume(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown intake session")
    return _answer_response(state)


def _answer_response(state) -> AnswerResponse:  # type: ignore[no-untyped-def]
    from shared.intake.question_bank import QUESTIONS_BY_ID

    question = QUESTIONS_BY_ID.get(state.current_question_id or "") if not state.completed else None
    return AnswerResponse(
        next_question=question.render(state.lang) if question else None,
        diagnostic_ready=state.completed,
        fired_probes=state.fired_probes,
        contradictions=state.contradictions,
    )
