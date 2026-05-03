from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

REQUEST_COUNT = Counter(
    "omscs_http_requests_total",
    "Total HTTP requests handled by OMSCS services.",
    ["service", "method", "path", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "omscs_http_request_duration_seconds",
    "HTTP request latency for OMSCS services.",
    ["service", "method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)

REQUESTS_IN_PROGRESS = Gauge(
    "omscs_http_requests_in_progress",
    "HTTP requests currently in progress for OMSCS services.",
    ["service", "method"],
)

SERVICE_INFO = Gauge(
    "omscs_service_info",
    "Static service metadata for OMSCS services.",
    ["service", "version"],
)


def instrument_fastapi_app(app: FastAPI, service_name: str) -> None:
    """Expose /metrics and add low-cardinality HTTP metrics to a FastAPI app."""
    if getattr(app.state, "observability_configured", False):
        return

    app.state.observability_configured = True
    SERVICE_INFO.labels(service=service_name, version=app.version).set(1)

    @app.middleware("http")
    async def prometheus_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _route_path(request)
        start = time.perf_counter()
        REQUESTS_IN_PROGRESS.labels(
            service=service_name,
            method=method,
        ).inc()

        try:
            response = await call_next(request)
        except Exception:
            path = _route_path(request)
            REQUEST_COUNT.labels(
                service=service_name,
                method=method,
                path=path,
                status_code="500",
            ).inc()
            REQUEST_LATENCY.labels(
                service=service_name,
                method=method,
                path=path,
            ).observe(time.perf_counter() - start)
            raise
        else:
            path = _route_path(request)
            REQUEST_COUNT.labels(
                service=service_name,
                method=method,
                path=path,
                status_code=str(response.status_code),
            ).inc()
            REQUEST_LATENCY.labels(
                service=service_name,
                method=method,
                path=path,
            ).observe(time.perf_counter() - start)
            return response
        finally:
            REQUESTS_IN_PROGRESS.labels(
                service=service_name,
                method=method,
            ).dec()

    app.mount("/metrics", make_asgi_app())


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    return request.url.path
