import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from strawberry.fastapi import GraphQLRouter
from app.core.logging import configure_logging
from app.api import recognition, lessons, tutor, quiz
from app.api.graphql_schema import schema, get_context
from app.obs.tracing import setup_tracing, tracer
from app.obs.metrics import REQUEST_LATENCY
from prometheus_client import make_asgi_app

configure_logging()
app = FastAPI(title="AnatoLens AI")


setup_tracing()
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        t = time.perf_counter()
        with tracer().start_as_current_span(f"{request.method} {request.url.path}") as span:
            resp = await call_next(request)
            route = getattr(request.scope.get("route"), "path", "unmatched")
            span.update_name(f"{request.method} {route}")
            span.set_attribute("http.status_code", resp.status_code)
        REQUEST_LATENCY.labels(route=route).observe(time.perf_counter() - t)
        return resp
app.add_middleware(TimingMiddleware)
app.mount("/metrics", make_asgi_app())


app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for m in (recognition, lessons, tutor, quiz):
    app.include_router(m.router)
app.include_router(GraphQLRouter(schema, context_getter=get_context), prefix="/graphql")

@app.get("/healthz")
def healthz(): return {"ok": True}
