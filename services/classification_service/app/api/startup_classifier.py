from __future__ import annotations

import os
from dataclasses import asdict
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from shared.application import router as classifier_router
from shared.application.startup_classifier import DEMO_TEST_CLASSIFIER, DEFAULT_CLASSIFIER
from shared.contracts.schemas import (
    StartupQuestionPayload,
    StartupStartRequest,
    StartupAnswerRequest,
)
from services.classification_service.app.services import classifier_service


USE_DEMO = os.environ.get("USE_DEMO_CLASSIFIER", "0").lower() in ("1", "true", "yes")
CLASSIFIER = DEMO_TEST_CLASSIFIER if USE_DEMO else DEFAULT_CLASSIFIER


router = APIRouter(prefix="/startup", tags=["startup-classifier"])


@router.get("/industries")
def list_industries_endpoint():
    """Industries the founder can pick to seed the PML questionnaire.

    ``start_session`` requires a valid ``industry_key`` (the tree is industry
    specific), so the caller must choose one of these up front.
    """
    return [
        {"key": ind.key, "name": ind.name, "family": ind.family}
        for ind in classifier_router.INDUSTRIES_BY_KEY.values()
    ]


@router.post("/session/start", response_model=StartupQuestionPayload)
def start_session_endpoint(payload: StartupStartRequest):
    try:
        # create a session id and persist session metadata
        session_id = str(uuid4())
        classifier_service.create_session(session_id, payload.industry_key, metadata={"initiated_by": "api"})
        q = classifier_router.start_session(payload.industry_key)
        q_dict = asdict(q)
        q_dict["session_id"] = session_id
        return q_dict
    except classifier_router.RouterError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.post("/session/answer")
def submit_answer_endpoint(payload: StartupAnswerRequest):
    try:
        backend_req = classifier_router.AnswerRequest(
            session_industry_key=payload.session_industry_key,
            node_id=payload.node_id,
            selected_option_index=payload.selected_option_index,
            free_text=payload.free_text,
            transcript_so_far=[t.model_dump(mode="json") if hasattr(t, "model_dump") else t for t in payload.transcript_so_far],
        )

        res = classifier_router.submit_answer(backend_req, classifier=CLASSIFIER)
        res_dict = asdict(res)
        # persist classification result into repo
        session_id = payload.session_id
        if session_id:
            classifier_service.persist_classification(session_id, res.node_id, getattr(res, "is_terminal", False), res_dict)
            res_dict["session_id"] = session_id
        return res_dict
    except classifier_router.RouterError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
