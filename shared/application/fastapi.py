from __future__ import annotations

from fastapi import FastAPI

from shared.config import get_settings
from shared.logging import CorrelationIdMiddleware, configure_logging


def create_service_app(title: str, service_name: str) -> FastAPI:
    settings = get_settings()
    configure_logging(service_name, settings.log_level)
    app = FastAPI(title=title, version="0.1.0")
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready", "service": service_name}

    return app
