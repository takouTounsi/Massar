import os

from fastapi.testclient import TestClient

# Ensure demo classifier is used in tests
os.environ["USE_DEMO_CLASSIFIER"] = "1"

from services.classification_service.app.main import app


def test_start_and_answer_flow():
    client = TestClient(app)

    # Start a session for Fintech (industry key "4")
    r = client.post("/api/v1/startup/session/start", json={"industry_key": "4"})
    assert r.status_code == 200, r.text
    q = r.json()
    assert "node_id" in q and "options" in q

    node_id = q["node_id"]
    # If the router asks for a company description first, provide free text
    if node_id == "company_description":
        answer_payload = {
            "session_industry_key": "4",
            "node_id": node_id,
            "free_text": "We build a SaaS analytics dashboard for small retailers, 50 paying customers, $10k/mo",
            "transcript_so_far": [],
        }
    else:
        # Choose first option (index 0) and submit
        answer_payload = {
            "session_industry_key": "4",
            "node_id": node_id,
            "selected_option_index": 0,
            "transcript_so_far": [],
        }

    r2 = client.post("/api/v1/startup/session/answer", json=answer_payload)
    assert r2.status_code == 200, r2.text
    res = r2.json()
    # Should be either a question or result
    assert "is_terminal" in res
