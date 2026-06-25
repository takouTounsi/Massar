from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from shared.config import get_settings
from shared.contracts.schemas import (
    AnalysisResult,
    DashboardResponse,
    IntakeAnswerRequest,
    IntakeAnswerResponse,
    IntakeSession,
    ProgressEvent,
    ProjectCreateRequest,
    ProjectProfile,
    Roadmap,
)
from shared.domain.blockers import RuleBasedBlockerDetector
from shared.domain.confidence import assess_confidence
from shared.domain.eligibility import evaluate_eligibility
from shared.domain.intake import AdaptiveIntakeEngine
from shared.domain.maturity import RuleBasedMaturityPredictor
from shared.domain.resources import match_resources
from shared.domain.roadmap import build_roadmap
from shared.domain.scoring import WeightedRuleScoreCalculator
from shared.security import DataEncryptor, DecryptionLease, DecryptionLeaseManager, EncryptedPayload


class InMemoryOrientationPipeline:
    """Small application service used by tests, demo scripts and MVP repositories."""

    def __init__(
        self,
        *,
        secure_storage: bool | None = None,
        encryption_key: str | None = None,
        lease_ttl_minutes: int | None = None,
    ) -> None:
        settings = get_settings()
        self.security_enabled = settings.data_encryption_enabled if secure_storage is None else secure_storage
        ttl_minutes = lease_ttl_minutes or settings.decryption_lease_ttl_minutes
        self.lease_manager = DecryptionLeaseManager(default_ttl_minutes=ttl_minutes)
        self.encryptor: DataEncryptor | None = None
        if self.security_enabled:
            key = encryption_key or settings.data_encryption_key
            if not key:
                raise ValueError("DATA_ENCRYPTION_KEY is required when DATA_ENCRYPTION_ENABLED=true")
            self.encryptor = DataEncryptor(key, key_id=settings.data_encryption_key_id)

        self.projects: dict[UUID, ProjectProfile] = {}
        self.encrypted_projects: dict[UUID, EncryptedPayload] = {}
        self.sessions: dict[UUID, IntakeSession] = {}
        self.project_session: dict[UUID, UUID] = {}
        self.analyses: dict[UUID, AnalysisResult] = {}
        self.encrypted_analyses: dict[UUID, EncryptedPayload] = {}
        self.progress_events: dict[UUID, list[ProgressEvent]] = {}
        self.intake = AdaptiveIntakeEngine()
        self.maturity = RuleBasedMaturityPredictor()
        self.scoring = WeightedRuleScoreCalculator()
        self.blockers = RuleBasedBlockerDetector()

    def create_project(self, request: ProjectCreateRequest) -> ProjectProfile:
        profile = ProjectProfile(
            country=request.country,
            region=request.region,
            actor_type=request.actor_type,
            business_type=request.business_type,
            sector=request.sector,
            sub_sector=request.sub_sector,
            declared_stage=request.declared_stage,
            primary_goal=request.primary_goal,
        )
        self._store_project(profile)
        self.progress_events[profile.project_id] = []
        return profile

    def get_project(self, project_id: UUID) -> ProjectProfile:
        if not self.security_enabled:
            return self.projects[project_id]
        lease = self.create_project_decryption_lease(project_id, purpose="profile:read")
        return self.get_project_for_lease(project_id, lease.lease_id, purpose="profile:read")

    def update_project(self, project_id: UUID, patch: dict[str, Any]) -> ProjectProfile:
        current = self.get_project(project_id)
        payload = current.model_dump()
        patch_payload = dict(patch)
        extra_answers = dict(payload.get("extra_answers", {}))
        incoming_extra = patch_payload.pop("extra_answers", None)
        if isinstance(incoming_extra, dict):
            extra_answers.update(incoming_extra)
        payload.update(patch_payload)
        payload["extra_answers"] = extra_answers
        payload["version"] = current.version + 1
        payload["updated_at"] = datetime.now(UTC)
        payload["history"] = [
            *current.history,
            {"version": current.version, "updated_at": current.updated_at.isoformat()},
        ]
        updated = ProjectProfile.model_validate(payload)
        self._store_project(updated)
        return updated

    def start_intake(self, project_id: UUID) -> IntakeSession:
        profile = self.get_project(project_id)
        session = self.intake.start(profile)
        self.sessions[session.session_id] = session
        self.project_session[project_id] = session.session_id
        return session

    def answer_intake(self, project_id: UUID, answer: IntakeAnswerRequest) -> IntakeAnswerResponse:
        profile = self.get_project(project_id)
        session_id = answer.session_id or self.project_session[project_id]
        session = self.sessions[session_id]
        response = self.intake.answer(profile, session, answer.question_code, answer.value)
        self.sessions[response.session.session_id] = response.session
        self.update_project(project_id, dict(response.profile_patch))
        return response

    def run_analysis(self, project_id: UUID) -> AnalysisResult:
        if self.security_enabled:
            lease = self.create_project_decryption_lease(project_id, purpose="analysis")
            profile = self.get_project_for_lease(project_id, lease.lease_id, purpose="analysis")
        else:
            profile = self.get_project(project_id)
        maturity = self.maturity.predict(profile)
        scores = self.scoring.calculate(profile)
        blockers = self.blockers.detect(profile, maturity)
        confidence = assess_confidence(profile, maturity, scores, blockers)
        resources = match_resources(profile, maturity, scores, blockers)
        eligibility = evaluate_eligibility(profile, resources)
        roadmap = build_roadmap(profile, blockers, scores, resources, eligibility)
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
                    f"gap is {maturity.gap_level}; "
                    f"{len(blockers.blockers)} blockers were prioritized."
                )
            },
        )
        self.save_analysis(project_id, analysis)
        return analysis

    def save_analysis(self, project_id: UUID, analysis: AnalysisResult) -> AnalysisResult:
        if project_id != analysis.project_id:
            raise ValueError("Analysis project_id does not match target project_id")
        self._store_analysis(analysis)
        return analysis

    def dashboard(self, project_id: UUID) -> DashboardResponse:
        return DashboardResponse(
            project_id=project_id,
            profile=self.get_project(project_id),
            analysis=self._load_analysis(project_id, purpose="dashboard"),
            progress_events=self.progress_events.get(project_id, []),
        )

    def roadmap(self, project_id: UUID) -> Roadmap:
        analysis = self._load_analysis(project_id, purpose="roadmap")
        if analysis is None:
            raise KeyError(project_id)
        return analysis.roadmap

    def complete_action(self, project_id: UUID, action_id: str) -> DashboardResponse:
        event = ProgressEvent(project_id=project_id, action_id=action_id)
        self.progress_events.setdefault(project_id, []).append(event)
        analysis = self._load_analysis(project_id, purpose="progress:update")
        if analysis is not None:
            for action in analysis.roadmap.actions:
                if action.id == action_id:
                    action.status = "DONE"  # type: ignore[assignment]
            self._store_analysis(analysis)
        return self.dashboard(project_id)

    def create_project_decryption_lease(
        self,
        project_id: UUID,
        *,
        purpose: str = "analysis",
        ttl: timedelta | None = None,
    ) -> DecryptionLease:
        return self.lease_manager.create_lease(subject_id=str(project_id), purpose=purpose, ttl=ttl)

    def get_project_for_lease(
        self,
        project_id: UUID,
        lease_id: str,
        *,
        purpose: str = "analysis",
    ) -> ProjectProfile:
        if not self.security_enabled:
            return self.projects[project_id]
        self.lease_manager.validate(lease_id, subject_id=str(project_id), purpose=purpose)
        encrypted = self.encrypted_projects[project_id]
        assert self.encryptor is not None
        payload = self.encryptor.decrypt_json(encrypted, aad=self._project_aad(project_id))
        return ProjectProfile.model_validate(payload)

    def encrypted_project_record(self, project_id: UUID) -> dict[str, Any] | None:
        encrypted = self.encrypted_projects.get(project_id)
        return encrypted.model_dump(mode="json") if encrypted else None

    def encrypted_analysis_record(self, project_id: UUID) -> dict[str, Any] | None:
        encrypted = self.encrypted_analyses.get(project_id)
        return encrypted.model_dump(mode="json") if encrypted else None

    def _store_project(self, profile: ProjectProfile) -> None:
        if not self.security_enabled:
            self.projects[profile.project_id] = profile
            return
        assert self.encryptor is not None
        self.encrypted_projects[profile.project_id] = self.encryptor.encrypt_json(
            profile.model_dump(mode="json"),
            aad=self._project_aad(profile.project_id),
        )

    def _store_analysis(self, analysis: AnalysisResult) -> None:
        if not self.security_enabled:
            self.analyses[analysis.project_id] = analysis
            return
        assert self.encryptor is not None
        self.encrypted_analyses[analysis.project_id] = self.encryptor.encrypt_json(
            analysis.model_dump(mode="json"),
            aad=self._analysis_aad(analysis.project_id),
        )

    def _load_analysis(self, project_id: UUID, *, purpose: str) -> AnalysisResult | None:
        if not self.security_enabled:
            return self.analyses.get(project_id)
        encrypted = self.encrypted_analyses.get(project_id)
        if encrypted is None:
            return None
        lease = self.create_project_decryption_lease(project_id, purpose=purpose)
        self.lease_manager.validate(lease.lease_id, subject_id=str(project_id), purpose=purpose)
        assert self.encryptor is not None
        payload = self.encryptor.decrypt_json(encrypted, aad=self._analysis_aad(project_id))
        return AnalysisResult.model_validate(payload)

    @staticmethod
    def _project_aad(project_id: UUID) -> str:
        return f"project:{project_id}"

    @staticmethod
    def _analysis_aad(project_id: UUID) -> str:
        return f"analysis:{project_id}"
