import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

def setup_tracing(service_name: str = "anatolens") -> None:
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return  
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if os.getenv("OTEL_TRACES_EXPORTER") == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

def tracer() -> trace.Tracer:
    return trace.get_tracer("anatolens")
