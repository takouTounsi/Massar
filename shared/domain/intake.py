from __future__ import annotations

from uuid import UUID

from shared.contracts.enums import QuestionType
from shared.contracts.schemas import IntakeAnswerResponse, IntakeSession, ProjectProfile, Question
from shared.domain.probes import TenderReadinessProbe


class AdaptiveIntakeEngine:
    def __init__(self) -> None:
        self.probes = [TenderReadinessProbe()]

    def start(self, profile: ProjectProfile) -> IntakeSession:
        question = self.next_question(profile, asked=[])
        return IntakeSession(
            project_id=profile.project_id,
            asked_question_codes=[question.code] if question else [],
            next_question=question,
            activated_probes=self._activated_probes(profile),
            completed=question is None,
        )

    def answer(
        self,
        profile: ProjectProfile,
        session: IntakeSession,
        question_code: str,
        value: object,
    ) -> IntakeAnswerResponse:
        patch = self._patch_for_answer(question_code, value)
        updated = ProjectProfile.model_validate({**profile.model_dump(), **patch})
        asked = list(dict.fromkeys([*session.asked_question_codes, question_code]))
        question = self.next_question(updated, asked=asked)
        next_asked = asked + ([question.code] if question and question.code not in asked else [])
        completed = question is None
        new_session = IntakeSession(
            session_id=session.session_id,
            project_id=profile.project_id,
            asked_question_codes=next_asked,
            completed=completed,
            next_question=question,
            activated_probes=self._activated_probes(updated),
        )
        return IntakeAnswerResponse(
            session=new_session,
            profile_patch=patch,
            missing_required_fields=self._missing_minimum_fields(updated),
        )

    def next_question(self, profile: ProjectProfile, asked: list[str]) -> Question | None:
        for question in self.question_bank(profile):
            if question.code in asked:
                continue
            if not self._has_value(profile, question.code):
                return question
        return None

    def question_bank(self, profile: ProjectProfile) -> list[Question]:
        questions = [
            Question(
                id="profile_001",
                code="country",
                text={"fr": "Dans quel pays votre projet est-il base ?", "ar": "في أي بلد يوجد مشروعك؟"},
                type=QuestionType.SINGLE_CHOICE,
                options=["TN", "MA", "DZ"],
                tags=["profile"],
            ),
            Question(
                id="profile_002",
                code="business_type",
                text={"fr": "Quel type de parcours decrivez-vous ?", "ar": "ما نوع المشروع؟"},
                type=QuestionType.SINGLE_CHOICE,
                options=["traditional_business", "startup"],
                tags=["profile"],
            ),
            Question(
                id="profile_003",
                code="sector",
                text={"fr": "Quel est votre secteur principal ?", "ar": "ما هو القطاع الرئيسي؟"},
                type=QuestionType.TEXT,
                tags=["profile"],
            ),
            Question(
                id="profile_004",
                code="declared_stage",
                text={"fr": "A quel stade pensez-vous etre ?", "ar": "في أي مرحلة تعتقد أنك؟"},
                type=QuestionType.SINGLE_CHOICE,
                options=[
                    "IDEATION",
                    "MARKET_VALIDATION",
                    "STRUCTURATION",
                    "FUNDRAISING",
                    "LAUNCH_PLANNING",
                    "GROWTH",
                ],
                tags=["profile", "maturity"],
            ),
            Question(
                id="validation_001",
                code="has_mvp",
                text={"fr": "Avez-vous un MVP ou prototype testable ?", "ar": "هل لديك نموذج أولي قابل للاختبار؟"},
                type=QuestionType.BOOLEAN,
                tags=["market_validation"],
            ),
            Question(
                id="validation_002",
                code="paying_customers",
                text={"fr": "Combien de clients payants avez-vous ?", "ar": "كم عدد العملاء الدافعين؟"},
                type=QuestionType.INTEGER,
                validation={"min": 0},
                tags=["market_validation", "traction"],
            ),
            Question(
                id="validation_003",
                code="documented_interviews",
                text={"fr": "Combien d'entretiens clients documentes avez-vous ?", "ar": "كم مقابلة موثقة؟"},
                type=QuestionType.INTEGER,
                validation={"min": 0},
                tags=["market_validation"],
            ),
            Question(
                id="goal_001",
                code="primary_goal",
                text={"fr": "Quel est votre objectif principal ?", "ar": "ما هو الهدف الرئيسي؟"},
                type=QuestionType.SINGLE_CHOICE,
                options=["funding", "public_procurement", "export", "launch", "growth"],
                tags=["goal"],
            ),
            Question(
                id="score_001",
                code="process_automation_level",
                text={"fr": "Quel pourcentage de vos processus cles est automatise ?", "ar": "ما نسبة الأتمتة؟"},
                type=QuestionType.NUMBER,
                validation={"min": 0, "max": 1},
                tags=["scalability"],
            ),
            Question(
                id="score_002",
                code="market_size_known",
                text={"fr": "Avez-vous estime la taille de votre marche ?", "ar": "هل قدرت حجم السوق؟"},
                type=QuestionType.BOOLEAN,
                tags=["market"],
            ),
        ]
        for probe in self.probes:
            questions.extend(probe.questions(profile))
        return questions

    def _patch_for_answer(self, question_code: str, value: object) -> dict[str, object]:
        known_fields = set(ProjectProfile.model_fields)
        if question_code in known_fields:
            return {question_code: value}
        return {"extra_answers": {question_code: value}}

    def _has_value(self, profile: ProjectProfile, code: str) -> bool:
        value = getattr(profile, code, None)
        if value in (None, [], ""):
            return False
        return True

    def _activated_probes(self, profile: ProjectProfile) -> list[str]:
        return [probe.code for probe in self.probes if probe.should_activate(profile)]

    def _missing_minimum_fields(self, profile: ProjectProfile) -> list[str]:
        fields = ["country", "business_type", "declared_stage", "has_mvp", "paying_customers"]
        return [field for field in fields if getattr(profile, field, None) in (None, [], "")]


def get_session(sessions: dict[UUID, IntakeSession], session_id: UUID) -> IntakeSession:
    try:
        return sessions[session_id]
    except KeyError as exc:
        raise KeyError(f"Unknown intake session {session_id}") from exc
