"""HTTP metrics + structured logging for the FastAPI process."""

from __future__ import annotations

import logging
import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import bind_request_id, current_request_id

REQUESTS = Counter(
    "credroute_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)
REQUEST_SECONDS = Histogram(
    "credroute_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
DECISIONS = Counter(
    "credroute_decisions_total",
    "Credit decisions",
    ["decision"],
)

_logger = logging.getLogger("credroute")


def configure_logging() -> None:
    if _logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
        )
    )
    _logger.setLevel(logging.INFO)
    _logger.addHandler(handler)
    _logger.propagate = False


def record_decision(decision: str) -> None:
    DECISIONS.labels(decision=decision or "unknown").inc()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = bind_request_id(request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID"))
        started = time.perf_counter()
        path = request.url.path
        try:
            response = await call_next(request)
        except Exception:
            REQUESTS.labels(request.method, path, "500").inc()
            REQUEST_SECONDS.labels(request.method, path).observe(time.perf_counter() - started)
            _logger.exception(
                "request_failed request_id=%s method=%s path=%s",
                current_request_id(),
                request.method,
                path,
            )
            raise
        elapsed = time.perf_counter() - started
        REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        REQUEST_SECONDS.labels(request.method, path).observe(elapsed)
        response.headers["X-Request-Id"] = request_id
        if not path.startswith("/api/metrics"):
            _logger.info(
                "http_request request_id=%s method=%s path=%s status=%s latency_ms=%.1f",
                request_id,
                request.method,
                path,
                response.status_code,
                elapsed * 1000,
            )
        return response


def prometheus_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
