from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from app.core.logging import configure_logging
from app.api import recognition, lessons, tutor
from app.api.graphql_schema import schema, get_context

configure_logging()
app = FastAPI(title="AnatoLens AI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for m in (recognition, lessons, tutor):
    app.include_router(m.router)
app.include_router(GraphQLRouter(schema, context_getter=get_context), prefix="/graphql")

@app.get("/healthz")
def healthz(): return {"ok": True}
