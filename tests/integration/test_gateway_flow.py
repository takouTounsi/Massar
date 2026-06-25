from fastapi.testclient import TestClient

from services.api_gateway.app import main as gateway


DEMO_PROJECT_ID = "11111111-1111-4111-8111-111111111111"


def _client() -> TestClient:
    gateway.settings.orchestration_mode = "local"
    return TestClient(gateway.app)


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@massar.local", "password": "MassarDemo123!"},
    )
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def test_gateway_local_end_to_end_flow() -> None:
    client = _client()
    headers = _auth_headers(client)
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "country": "TN",
            "business_type": "startup",
            "sector": "technology",
            "declared_stage": "FUNDRAISING",
            "primary_goal": "funding",
        },
    ).json()
    project_id = project["project_id"]

    session = client.post(f"/api/v1/projects/{project_id}/intake/start", headers=headers).json()
    answers = {
        "has_mvp": True,
        "paying_customers": 0,
        "documented_interviews": 3,
        "process_automation_level": 0.2,
        "market_size_known": False,
    }
    while not session["completed"] and session["next_question"] is not None:
        code = session["next_question"]["code"]
        response = client.post(
            f"/api/v1/projects/{project_id}/intake/answer",
            headers=headers,
            json={
                "session_id": session["session_id"],
                "question_code": code,
                "value": answers.get(code, "technology"),
            },
        ).json()
        session = response["session"]

    analysis = client.post(f"/api/v1/projects/{project_id}/analysis/run", headers=headers).json()
    dashboard = client.get(f"/api/v1/projects/{project_id}/dashboard", headers=headers).json()
    action_id = analysis["roadmap"]["actions"][0]["id"]
    progress = client.post(
        f"/api/v1/projects/{project_id}/progress",
        headers=headers,
        json={"action_id": action_id},
    ).json()

    assert analysis["maturity"]["diagnosed_stage"] == "MARKET_VALIDATION"
    assert analysis["maturity"]["gap_level"] == "HIGH"
    assert len(analysis["scores"]["scores"]) == 5
    assert len(analysis["blockers"]["blockers"]) == 2
    assert len(analysis["resources"]) == 3
    assert dashboard["analysis"]["project_id"] == project_id
    assert progress["progress_events"][0]["action_id"] == action_id


def test_demo_roadmap_completion_updates_dashboard_progress() -> None:
    client = _client()
    headers = _auth_headers(client)

    generated = client.post(
        f"/api/v1/projects/{DEMO_PROJECT_ID}/roadmap/generate",
        headers=headers,
    )
    assert generated.status_code == 200
    generated_body = generated.json()
    action_id = generated_body["actions"][0]["id"]

    updated = client.patch(
        f"/api/v1/projects/{DEMO_PROJECT_ID}/roadmap/actions/{action_id}",
        headers=headers,
        json={"status": "COMPLETED"},
    )
    assert updated.status_code == 200

    fetched = client.get(f"/api/v1/projects/{DEMO_PROJECT_ID}/roadmap", headers=headers).json()
    dashboard = client.get(f"/api/v1/projects/{DEMO_PROJECT_ID}/dashboard", headers=headers).json()

    assert fetched["actions"][0]["id"] == action_id
    assert fetched["actions"][0]["status"] == "COMPLETED"
    assert dashboard["analysis"]["roadmap"]["actions"][0]["status"] == "COMPLETED"
    assert dashboard["analysis"]["progress"] > 18
