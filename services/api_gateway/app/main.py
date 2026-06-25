from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.application import InMemoryOrientationPipeline
from shared.application.fastapi import create_service_app
from shared.config import get_settings
from shared.contracts.schemas import (
    AnalysisResult,
    BlockerResult,
    CompositeScores,
    ConfidenceReport,
    DashboardResponse,
    EligibilityResult,
    IntakeAnswerRequest,
    IntakeAnswerResponse,
    IntakeSession,
    MaturityPrediction,
    ProjectCreateRequest,
    ProjectProfile,
    ResourceMatch,
    Roadmap,
)
from shared.demo_data import build_demo_dashboard, demo_profiles, get_demo_project, get_project_resources

from services.api_gateway.app.api.auth import router as auth_router
from services.api_gateway.app.auth.schemas import UserPublic
from services.api_gateway.app.dependencies import require_user
from services.roadmap_service.app.generator import generate_roadmap
from services.roadmap_service.app.repository import roadmap_repository
from services.roadmap_service.app.schemas import GeneratedRoadmap, RoadmapGenerationInput, RoadmapStatusPatch

settings = get_settings()
app = create_service_app("API Gateway / Orientation Orchestrator", "api_gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
local_pipeline = InMemoryOrientationPipeline()
gateway_sessions: dict[UUID, IntakeSession] = {}
project_sessions: dict[UUID, UUID] = {}
# Metadata index for uploaded PDF evidence, keyed by project. The file bytes
# live on disk under settings.intake_evidence_dir; this maps them back to the
# project / session / question they were attached to.
evidence_index: dict[UUID, list[dict[str, Any]]] = {}


class ProgressPayload(BaseModel):
    action_id: str


class AssistantPayload(BaseModel):
    message: str


class AdaptiveStartPayload(BaseModel):
    project_id: str | None = None
    lang: str = "fr"


class AdaptiveAnswerPayload(BaseModel):
    raw_answer: str
    question_id: str


async def _post(url: str, payload: dict[str, Any], request: Request) -> Any:
    headers = {"x-correlation-id": request.headers.get("x-correlation-id", "")}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json=payload, headers=headers)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _get(url: str, request: Request) -> Any:
    headers = {"x-correlation-id": request.headers.get("x-correlation-id", "")}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=headers)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _patch(url: str, payload: dict[str, Any], request: Request) -> Any:
    headers = {"x-correlation-id": request.headers.get("x-correlation-id", "")}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.patch(url, json=payload, headers=headers)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


def _http_mode() -> bool:
    return settings.orchestration_mode == "http"


def _profile_from_demo(project_id: UUID) -> ProjectProfile | None:
    demo_project = get_demo_project(str(project_id))
    if not demo_project:
        return None
    allowed = {field for field in ProjectProfile.model_fields}
    payload = {key: value for key, value in demo_project.items() if key in allowed}
    return ProjectProfile.model_validate(payload)


def _roadmap_payload_from_demo(project_id: UUID) -> RoadmapGenerationInput | None:
    dashboard_data = build_demo_dashboard(str(project_id))
    if not dashboard_data:
        return None
    project = dashboard_data["project"]
    analysis = dashboard_data["analysis"]
    resources = analysis.get("resources", [])
    return RoadmapGenerationInput(
        project_id=project_id,
        country=project["country"],
        business_type=project["business_type"],
        sector=project["sector"],
        primary_goal=project["primary_goal"],
        declared_stage=analysis["declared_stage"],
        diagnosed_stage=analysis["diagnosed_stage"],
        maturity_confidence=analysis["maturity_confidence"],
        scores=analysis["scores"],
        score_details=analysis.get("score_details", {}),
        blockers=analysis.get("blockers", []),
        resources=[
            {
                "resource_id": resource["resource_id"],
                "name": resource["name"],
                "institution": resource["institution"],
                "category": resource["category"],
                "eligibility_status": resource["eligibility_status"],
                "source_url": resource["source_url"],
            }
            for resource in resources
        ],
        missing_fields=analysis.get("missing_fields", []),
    )


def _normalize_action_status(status: str) -> str:
    return "COMPLETED" if status == "DONE" else status


def _demo_progress_with_roadmap(demo_progress: Any, generated: GeneratedRoadmap) -> int:
    try:
        fallback = int(demo_progress)
    except (TypeError, ValueError):
        fallback = 0
    if not generated.actions:
        return fallback
    completed = sum(1 for action in generated.actions if action.status in {"COMPLETED", "DONE"})
    generated_progress = round((completed / len(generated.actions)) * 100)
    return max(fallback, generated_progress)


async def _get_generated_roadmap(project_id: UUID, request: Request) -> GeneratedRoadmap | None:
    generated = roadmap_repository.get(project_id)
    if generated is not None:
        return generated
    if not _http_mode():
        return None
    try:
        data = await _get(f"{settings.roadmap_service_url}/api/v1/projects/{project_id}/roadmap", request)
    except HTTPException:
        return None
    return GeneratedRoadmap.model_validate(data)


async def _record_completed_action(project_id: UUID, action_id: str, request: Request) -> None:
    if not _http_mode():
        return
    try:
        await _post(
            f"{settings.progress_service_url}/progress/actions/{action_id}/complete",
            {"project_id": str(project_id)},
            request,
        )
    except (HTTPException, httpx.HTTPError):
        return


@app.get("/api/v1/projects")
async def list_projects(current_user: UserPublic = Depends(require_user)) -> list[dict[str, Any]]:
    return demo_profiles()


@app.post("/api/v1/projects", response_model=ProjectProfile)
async def create_project(
    payload: ProjectCreateRequest,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> ProjectProfile:
    if not _http_mode():
        return local_pipeline.create_project(payload)
    data = await _post(
        f"{settings.profile_service_url}/profiles/projects",
        payload.model_dump(mode="json"),
        request,
    )
    return ProjectProfile.model_validate(data)


@app.get("/api/v1/projects/{project_id}", response_model=ProjectProfile)
async def get_project(
    project_id: UUID,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> ProjectProfile:
    if not _http_mode():
        try:
            return local_pipeline.get_project(project_id)
        except KeyError:
            demo_profile = _profile_from_demo(project_id)
            if demo_profile is not None:
                return demo_profile
            raise
    try:
        data = await _get(f"{settings.profile_service_url}/profiles/projects/{project_id}", request)
        return ProjectProfile.model_validate(data)
    except HTTPException:
        demo_profile = _profile_from_demo(project_id)
        if demo_profile is not None:
            return demo_profile
        raise


@app.post("/api/v1/projects/{project_id}/intake/start", response_model=IntakeSession)
async def start_intake(
    project_id: UUID,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> IntakeSession:
    if not _http_mode():
        return local_pipeline.start_intake(project_id)
    profile = await get_project(project_id, request)
    data = await _post(
        f"{settings.intake_service_url}/intake/start",
        profile.model_dump(mode="json"),
        request,
    )
    session = IntakeSession.model_validate(data)
    gateway_sessions[session.session_id] = session
    project_sessions[project_id] = session.session_id
    return session


@app.post("/api/v1/projects/{project_id}/intake/answer", response_model=IntakeAnswerResponse)
async def answer_intake(
    project_id: UUID,
    payload: IntakeAnswerRequest,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> IntakeAnswerResponse:
    if not _http_mode():
        return local_pipeline.answer_intake(project_id, payload)
    profile = await get_project(project_id, request)
    session_id = payload.session_id or project_sessions.get(project_id)
    if session_id is None or session_id not in gateway_sessions:
        raise HTTPException(status_code=409, detail="No active intake session")
    session = gateway_sessions[session_id]
    data = await _post(
        f"{settings.intake_service_url}/intake/answer",
        {
            "profile": profile.model_dump(mode="json"),
            "session": session.model_dump(mode="json"),
            "question_code": payload.question_code,
            "value": payload.value,
        },
        request,
    )
    response = IntakeAnswerResponse.model_validate(data)
    gateway_sessions[response.session.session_id] = response.session
    project_sessions[project_id] = response.session.session_id
    await _patch(
        f"{settings.profile_service_url}/profiles/projects/{project_id}",
        {"patch": response.profile_patch},
        request,
    )
    return response


def _evidence_dir(project_id: UUID) -> Path:
    return Path(settings.intake_evidence_dir) / str(project_id)


@app.post("/api/v1/projects/{project_id}/intake/evidence")
async def upload_intake_evidence(
    project_id: UUID,
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    question_code: str | None = Form(default=None),
    current_user: UserPublic = Depends(require_user),
) -> dict[str, Any]:
    """Store a PDF evidence attachment and link it to the project/session.

    Scope is upload + storage + association only (no PDF parsing/extraction).
    """
    filename = file.filename or "evidence.pdf"
    is_pdf = file.content_type == "application/pdf" or filename.lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(contents) > settings.intake_evidence_max_bytes:
        limit_mb = settings.intake_evidence_max_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File exceeds the {limit_mb} MB limit.")
    # Guard against non-PDF payloads disguised by a .pdf name / content-type.
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")

    evidence_id = uuid4()
    target_dir = _evidence_dir(project_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / f"{evidence_id}.pdf").write_bytes(contents)

    linked_session = session_id or project_sessions.get(project_id)
    record = {
        "evidence_id": str(evidence_id),
        "project_id": str(project_id),
        "session_id": str(linked_session) if linked_session else None,
        "question_code": question_code,
        "filename": filename,
        "content_type": "application/pdf",
        "size": len(contents),
        "uploaded_at": datetime.now(UTC).isoformat(),
    }
    evidence_index.setdefault(project_id, []).append(record)
    return record


@app.get("/api/v1/projects/{project_id}/intake/evidence")
async def list_intake_evidence(
    project_id: UUID,
    session_id: str | None = None,
    current_user: UserPublic = Depends(require_user),
) -> list[dict[str, Any]]:
    records = evidence_index.get(project_id, [])
    if session_id:
        records = [item for item in records if item.get("session_id") == session_id]
    return records


# --- Adaptive Intake Engine (evidence-ledger driven) ---
# These always proxy to the intake service: the adaptive engine is service-only
# (no in-memory pipeline equivalent). The frontend talks to the gateway so it
# benefits from CORS and a single public origin.


@app.post("/api/v1/intake/sessions")
async def adaptive_create_session(payload: AdaptiveStartPayload, request: Request) -> Any:
    return await _post(
        f"{settings.intake_service_url}/sessions", payload.model_dump(mode="json"), request
    )


@app.post("/api/v1/intake/sessions/{session_id}/answers")
async def adaptive_answer(
    session_id: UUID, payload: AdaptiveAnswerPayload, request: Request
) -> Any:
    return await _post(
        f"{settings.intake_service_url}/sessions/{session_id}/answers",
        payload.model_dump(mode="json"),
        request,
    )


@app.get("/api/v1/intake/sessions/{session_id}/state")
async def adaptive_state(session_id: UUID, request: Request) -> Any:
    return await _get(f"{settings.intake_service_url}/sessions/{session_id}/state", request)


@app.get("/api/v1/intake/sessions/{session_id}/diagnosis")
async def adaptive_diagnosis(session_id: UUID, request: Request) -> Any:
    return await _get(f"{settings.intake_service_url}/sessions/{session_id}/diagnosis", request)


@app.post("/api/v1/intake/sessions/{session_id}/resume")
async def adaptive_resume(session_id: UUID, request: Request) -> Any:
    return await _post(
        f"{settings.intake_service_url}/sessions/{session_id}/resume", {}, request
    )


@app.post("/api/v1/intake/sessions/{session_id}/pml")
async def adaptive_apply_pml(session_id: UUID, payload: dict[str, Any], request: Request) -> Any:
    """Feed the Classification Service's terminal PML payload into the declared/gap side.

    The raw payload is forwarded verbatim; the intake service maps it at the
    boundary (``adapt_pml``) and writes it ONLY to ``declared_stage`` (the
    perceived side). It never enters the evidence ledger, gates, or selection.
    """
    return await _post(
        f"{settings.intake_service_url}/sessions/{session_id}/pml", payload, request
    )


# --- Classification Service (PML / perceived self-assessment) proxies ---
# The founder's self-assessment is produced by the dedicated classification
# service's branching questionnaire. Its terminal ``phase`` is the PERCEIVED
# maturity; it flows into the intake engine ONLY via the /pml endpoint above.


@app.get("/api/v1/classification/industries")
async def classification_industries(request: Request) -> Any:
    return await _get(f"{settings.classification_service_url}/api/v1/startup/industries", request)


@app.post("/api/v1/classification/session/start")
async def classification_start(payload: dict[str, Any], request: Request) -> Any:
    return await _post(
        f"{settings.classification_service_url}/api/v1/startup/session/start", payload, request
    )


@app.post("/api/v1/classification/session/answer")
async def classification_answer(payload: dict[str, Any], request: Request) -> Any:
    return await _post(
        f"{settings.classification_service_url}/api/v1/startup/session/answer", payload, request
    )


@app.post("/api/v1/projects/{project_id}/analysis/run", response_model=AnalysisResult)
async def run_analysis(
    project_id: UUID,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> AnalysisResult:
    if not _http_mode():
        return local_pipeline.run_analysis(project_id)

    profile = await get_project(project_id, request)
    maturity = MaturityPrediction.model_validate(
        await _post(
            f"{settings.maturity_service_url}/maturity/predict",
            profile.model_dump(mode="json"),
            request,
        )
    )
    scores = CompositeScores.model_validate(
        await _post(
            f"{settings.scoring_service_url}/scores/calculate",
            profile.model_dump(mode="json"),
            request,
        )
    )
    blockers = BlockerResult.model_validate(
        await _post(
            f"{settings.blocker_service_url}/blockers/detect",
            {"profile": profile.model_dump(mode="json"), "maturity": maturity.model_dump(mode="json")},
            request,
        )
    )
    confidence = ConfidenceReport.model_validate(
        await _post(
            f"{settings.confidence_service_url}/confidence/assess",
            {
                "profile": profile.model_dump(mode="json"),
                "maturity": maturity.model_dump(mode="json"),
                "scores": scores.model_dump(mode="json"),
                "blockers": blockers.model_dump(mode="json"),
            },
            request,
        )
    )
    resources = [
        ResourceMatch.model_validate(item)
        for item in await _post(
            f"{settings.resource_service_url}/resources/match",
            {
                "profile": profile.model_dump(mode="json"),
                "maturity": maturity.model_dump(mode="json"),
                "scores": scores.model_dump(mode="json"),
                "blockers": blockers.model_dump(mode="json"),
                "limit": 3,
            },
            request,
        )
    ]
    eligibility = [
        EligibilityResult.model_validate(item)
        for item in await _post(
            f"{settings.eligibility_service_url}/eligibility/check",
            {
                "profile": profile.model_dump(mode="json"),
                "resources": [resource.model_dump(mode="json") for resource in resources],
            },
            request,
        )
    ]
    roadmap = Roadmap.model_validate(
        await _post(
            f"{settings.roadmap_service_url}/roadmaps/build",
            {
                "profile": profile.model_dump(mode="json"),
                "blockers": blockers.model_dump(mode="json"),
                "scores": scores.model_dump(mode="json"),
                "resources": [resource.model_dump(mode="json") for resource in resources],
                "eligibility": [item.model_dump(mode="json") for item in eligibility],
            },
            request,
        )
    )
    analysis = AnalysisResult(
        project_id=project_id,
        profile=profile,
        maturity=maturity,
        scores=scores,
        blockers=blockers,
        confidence=confidence,
        resources=resources,
        eligibility=eligibility,
        roadmap=roadmap,
        explanations={
            "short": (
                f"Diagnosed stage is {maturity.diagnosed_stage}; "
                f"gap is {maturity.gap_level}; {len(blockers.blockers)} blockers were prioritized."
            )
        },
    )
    await _post(
        f"{settings.profile_service_url}/profiles/projects/{project_id}/analysis",
        analysis.model_dump(mode="json"),
        request,
    )
    return analysis


@app.get("/api/v1/projects/{project_id}/dashboard")
async def dashboard(
    project_id: UUID,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> dict[str, Any] | DashboardResponse:
    demo_dashboard = build_demo_dashboard(str(project_id))
    if demo_dashboard is not None:
        generated = await _get_generated_roadmap(project_id, request)
        if generated is not None:
            demo_dashboard["analysis"]["roadmap"] = generated.model_dump(mode="json")
            demo_dashboard["analysis"]["progress"] = _demo_progress_with_roadmap(
                demo_dashboard["analysis"].get("progress"),
                generated,
            )
        return demo_dashboard
    if not _http_mode():
        return local_pipeline.dashboard(project_id)
    data = await _get(f"{settings.profile_service_url}/profiles/projects/{project_id}/dashboard", request)
    return DashboardResponse.model_validate(data)


@app.get("/api/v1/projects/{project_id}/resources")
async def resources(
    project_id: UUID,
    current_user: UserPublic = Depends(require_user),
) -> list[dict[str, Any]]:
    return get_project_resources(str(project_id))


@app.post("/api/v1/projects/{project_id}/roadmap/generate", response_model=GeneratedRoadmap)
async def generate_project_roadmap(
    project_id: UUID,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> GeneratedRoadmap:
    payload = _roadmap_payload_from_demo(project_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Demo project data not found")
    if not _http_mode():
        return roadmap_repository.save(generate_roadmap(payload))
    data = await _post(
        f"{settings.roadmap_service_url}/api/v1/projects/{project_id}/roadmap/generate",
        payload.model_dump(mode="json"),
        request,
    )
    return GeneratedRoadmap.model_validate(data)


@app.get("/api/v1/projects/{project_id}/roadmap")
async def roadmap(
    project_id: UUID,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> Roadmap | GeneratedRoadmap:
    generated = await _get_generated_roadmap(project_id, request)
    if generated is not None:
        return generated
    if _roadmap_payload_from_demo(project_id) is not None:
        return await generate_project_roadmap(project_id, request, current_user)
    if not _http_mode():
        return local_pipeline.roadmap(project_id)
    try:
        data = await _get(f"{settings.roadmap_service_url}/api/v1/projects/{project_id}/roadmap", request)
        return GeneratedRoadmap.model_validate(data)
    except HTTPException:
        data = await _get(f"{settings.profile_service_url}/profiles/projects/{project_id}/roadmap", request)
        return Roadmap.model_validate(data)


@app.patch("/api/v1/projects/{project_id}/roadmap/actions/{action_id}", response_model=GeneratedRoadmap)
async def patch_roadmap_action(
    project_id: UUID,
    action_id: str,
    payload: RoadmapStatusPatch,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> GeneratedRoadmap:
    status_value = _normalize_action_status(payload.status)
    if not _http_mode():
        roadmap = roadmap_repository.patch_action(project_id, action_id, status_value)
        if roadmap is None:
            raise HTTPException(status_code=404, detail="Roadmap or action not found")
        return roadmap
    data = await _patch(
        f"{settings.roadmap_service_url}/api/v1/projects/{project_id}/roadmap/actions/{action_id}",
        {"status": status_value},
        request,
    )
    if status_value == "COMPLETED":
        await _record_completed_action(project_id, action_id, request)
    return GeneratedRoadmap.model_validate(data)


@app.post("/api/v1/projects/{project_id}/roadmap/regenerate", response_model=GeneratedRoadmap)
async def regenerate_project_roadmap(
    project_id: UUID,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> GeneratedRoadmap:
    return await generate_project_roadmap(project_id, request, current_user)


@app.post("/api/v1/projects/{project_id}/progress", response_model=DashboardResponse)
async def progress(
    project_id: UUID,
    payload: ProgressPayload,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> DashboardResponse:
    if not _http_mode():
        return local_pipeline.complete_action(project_id, payload.action_id)
    await _post(
        f"{settings.progress_service_url}/progress/actions/{payload.action_id}/complete",
        {"project_id": str(project_id)},
        request,
    )
    data = await _post(
        f"{settings.profile_service_url}/profiles/projects/{project_id}/progress",
        {"action_id": payload.action_id},
        request,
    )
    return DashboardResponse.model_validate(data)


@app.post("/api/v1/projects/{project_id}/assistant")
async def assistant(
    project_id: UUID,
    payload: AssistantPayload,
    request: Request,
    current_user: UserPublic = Depends(require_user),
) -> dict[str, Any]:
    current_dashboard = await dashboard(project_id, request, current_user)
    if isinstance(current_dashboard, dict):
        stage = current_dashboard.get("analysis", {}).get("diagnosed_stage", "UNKNOWN")
    else:
        stage = (
            current_dashboard.analysis.maturity.diagnosed_stage
            if current_dashboard.analysis is not None
            else "UNKNOWN"
        )
    return {
        "project_id": str(project_id),
        "answer": (
            "This assistant layer is secondary. "
            f"Based on the current structured profile, the diagnosed stage is {stage}. "
            f"Question received: {payload.message}"
        ),
    }
