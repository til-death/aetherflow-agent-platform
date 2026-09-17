from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import settings

_tracer = trace.get_tracer("shuiliu.runtime")
_configured = False


def configure_telemetry(app: FastAPI) -> None:
    """Enable OTLP export only when explicitly configured."""
    global _configured
    if _configured or not settings.OTEL_ENABLED:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.OTEL_SERVICE_NAME,
                "service.version": "runtime-v1",
                "deployment.environment": settings.ENVIRONMENT,
            }
        )
    )
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT))
        )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    _configured = True


@contextmanager
def stage_span(
    stage: str,
    *,
    run_id: str | None = None,
    agent_name: str | None = None,
    tool_name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Create a no-op span when telemetry is disabled and a real span when enabled."""
    with _tracer.start_as_current_span(f"agent.{stage}") as span:
        span.set_attribute("agent.stage", stage)
        if run_id:
            span.set_attribute("agent.run_id", run_id)
        if agent_name:
            span.set_attribute("agent.agent_name", agent_name)
        if tool_name:
            span.set_attribute("agent.tool_name", tool_name)
        for key, value in (attributes or {}).items():
            if value is not None and isinstance(value, (str, int, float, bool)):
                span.set_attribute(key, value)
        yield span
