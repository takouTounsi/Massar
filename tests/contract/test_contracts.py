from shared.contracts.schemas import ProjectCreateRequest, ProjectProfile


def test_project_create_contract_can_create_profile() -> None:
    payload = ProjectCreateRequest(country="TN", business_type="startup", declared_stage="FUNDRAISING")
    profile = ProjectProfile(**payload.model_dump())

    assert profile.country == "TN"
    assert profile.business_type == "startup"
    assert profile.declared_stage == "FUNDRAISING"
