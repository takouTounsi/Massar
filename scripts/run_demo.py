from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.application import InMemoryOrientationPipeline  # noqa: E402
from shared.contracts.enums import BusinessType, CountryCode, MaturityStage  # noqa: E402
from shared.contracts.schemas import IntakeAnswerRequest, ProjectCreateRequest  # noqa: E402


def main() -> None:
    pipeline = InMemoryOrientationPipeline()
    project = pipeline.create_project(
        ProjectCreateRequest(
            country=CountryCode.TN,
            business_type=BusinessType.STARTUP,
            sector="technology",
            sub_sector="saas",
            declared_stage=MaturityStage.FUNDRAISING,
            primary_goal="funding",
        )
    )
    session = pipeline.start_intake(project.project_id)
    demo_answers = {
        "has_mvp": True,
        "paying_customers": 0,
        "documented_interviews": 3,
        "process_automation_level": 0.2,
        "market_size_known": False,
    }
    while not session.completed and session.next_question is not None:
        code = session.next_question.code
        value = demo_answers.get(code, "technology")
        response = pipeline.answer_intake(
            project.project_id,
            IntakeAnswerRequest(session_id=session.session_id, question_code=code, value=value),
        )
        session = response.session

    pipeline.update_project(
        project.project_id,
        {
            "legal_form": "SUARL",
            "formalization_status": "formalized",
            "has_revenue": False,
            "market_validation_evidence": [],
            "revenue_model_clarity": 45,
            "competition_understanding": 50,
            "team_size": 3,
        },
    )
    analysis = pipeline.run_analysis(project.project_id)
    summary = {
        "project_id": str(project.project_id),
        "diagnosed_stage": analysis.maturity.diagnosed_stage,
        "declared_stage": analysis.maturity.declared_stage,
        "gap_level": analysis.maturity.gap_level,
        "score_names": [score.name for score in analysis.scores.scores],
        "blockers": [blocker.type for blocker in analysis.blockers.blockers],
        "resource_count": len(analysis.resources),
        "eligibility_statuses": [item.status for item in analysis.eligibility],
        "roadmap_actions": [action.title for action in analysis.roadmap.actions],
        "dashboard_ready": pipeline.dashboard(project.project_id).analysis is not None,
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
