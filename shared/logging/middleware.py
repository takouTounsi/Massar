from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

try:
    import structlog
except ModuleNotFoundError:  # pragma: no cover - exercised only in minimal local envs
    structlog = None  # type: ignore[assignment]


def configure_logging(service_name: str, level: str = "INFO") -> None:
    logging.basicConfig(level=level)
    if structlog is None:
        logging.getLogger(service_name).setLevel(level)
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service_name)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get("x-correlation-id", str(uuid4()))
        if structlog is not None:
            structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        started = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["x-correlation-id"] = correlation_id
        if structlog is not None:
            structlog.get_logger().info(
                "request_completed",
                operation=f"{request.method} {request.url.path}",
                latency_ms=latency_ms,
                status_code=response.status_code,
            )
        else:
            logging.info(
                "request_completed operation=%s latency_ms=%s status_code=%s correlation_id=%s",
                f"{request.method} {request.url.path}",
                latency_ms,
                response.status_code,
                correlation_id,
            )
        return response
