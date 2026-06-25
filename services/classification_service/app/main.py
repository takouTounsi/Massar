from __future__ import annotations

from shared.application.fastapi import create_service_app

app = create_service_app("Classification Service", "classification_service")

# The classification service exposes the startup classifier router (stateless)
from .api import startup_classifier  # noqa: E402

app.include_router(startup_classifier.router, prefix="/api/v1")
