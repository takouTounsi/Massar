import os
from fastapi.testclient import TestClient

# Use demo classifier and in-memory repo for tests
os.environ["USE_DEMO_CLASSIFIER"] = "1"

from services.classification_service.app.main import app
from services.classification_service.app.services import classifier_service


def test_session_and_result_persisted():
    client = TestClient(app)

    # Start a session
    r = client.post("/api/v1/startup/session/start", json={"industry_key": "4"})
    assert r.status_code == 200, r.text
    q = r.json()
    assert "session_id" in q
    session_id = q["session_id"]

    # Submit an answer. If initial node asks for company description, provide free text first.
    node_id = q["node_id"]
    if node_id == "company_description":
        answer_payload = {
            "session_industry_key": "4",
            "session_id": session_id,
            "node_id": node_id,
            "free_text": "We run a B2B marketplace for local services, 20 customers, recurring revenue",
            "transcript_so_far": [],
        }
    else:
        answer_payload = {
            "session_industry_key": "4",
            "session_id": session_id,
            "node_id": node_id,
            "selected_option_index": 0,
            "transcript_so_far": [],
        }

    r2 = client.post("/api/v1/startup/session/answer", json=answer_payload)
    assert r2.status_code == 200, r2.text
    res = r2.json()

    # Fetch session from service layer (in-memory repo)
    sess = classifier_service.fetch_session(session_id)
    assert sess is not None
    assert sess.get("session_id") == session_id
    # results list should contain at least one entry
    assert len(sess.get("results", [])) >= 1
