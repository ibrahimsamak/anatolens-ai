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

def setup_mlflow() -> None:
    import logging
    import mlflow
    from app.core.config import settings
    if not (settings.mlflow_tracing and settings.mlflow_tracking_uri):
        mlflow.tracing.disable()
        return
    try:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment)
        mlflow.langchain.autolog()
    except Exception as e:
        mlflow.tracing.disable()
        logging.getLogger(__name__).warning("MLflow tracing disabled: %s", e)

def tracer() -> trace.Tracer:
    return trace.get_tracer("anatolens")
