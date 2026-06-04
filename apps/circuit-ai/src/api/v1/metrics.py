from __future__ import annotations

from typing import Any, Dict

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "circuit_api_requests_total",
    "Total number of HTTP requests handled by the enhanced API surface.",
    ["endpoint", "method", "status_code"],
)

REQUEST_DURATION = Histogram(
    "circuit_api_request_duration_seconds",
    "Latency of HTTP requests handled by the enhanced API surface.",
    ["endpoint", "method"],
)

ERROR_COUNT = Counter(
    "circuit_api_errors_total",
    "Total number of application errors handled by the enhanced API surface.",
    ["endpoint", "error_type"],
)

ANALYSIS_COUNT = Counter(
    "circuit_analysis_requests_total",
    "Total number of enhanced PCB analysis requests.",
    ["backend", "status"],
)

ANALYSIS_DURATION = Histogram(
    "circuit_analysis_duration_seconds",
    "Latency of enhanced PCB analysis requests.",
    ["backend"],
)

ACTIVE_CONNECTIONS = Gauge(
    "circuit_active_connections",
    "Number of active WebSocket connections on the enhanced API surface.",
)


def record_request_metrics(endpoint: str, method: str, status_code: int, duration: float) -> None:
    """Record request count and latency for an HTTP route."""
    REQUEST_COUNT.labels(endpoint=endpoint, method=method, status_code=str(status_code)).inc()
    REQUEST_DURATION.labels(endpoint=endpoint, method=method).observe(duration)


def record_error_metrics(error_type: str, endpoint: str) -> None:
    """Record an application-level error."""
    ERROR_COUNT.labels(endpoint=endpoint, error_type=error_type or "unknown").inc()


def record_analysis_metrics(backend: str, duration: float, success: bool) -> None:
    """Record enhanced analysis-specific request metrics."""
    ANALYSIS_COUNT.labels(backend=backend or "default", status="success" if success else "failure").inc()
    if success:
        ANALYSIS_DURATION.labels(backend=backend or "default").observe(duration)


def set_active_connections(count: int) -> None:
    """Update the live WebSocket connection gauge."""
    ACTIVE_CONNECTIONS.set(max(0, count))


def get_metrics_response() -> Response:
    """Expose Prometheus metrics for the enhanced API surface."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def get_circuit_ai_metrics() -> Dict[str, Any]:
    """Return a compact metrics summary for debugging or lightweight dashboards."""
    return {
        "active_connections": ACTIVE_CONNECTIONS._value.get(),
    }
