import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse
from app.api.deps import get_db, get_anatomy_graph
from app.rag.graphrag import explain_structure
from app.guardrails.pipeline import check_input

router = APIRouter(prefix="/api/v1")

class ExplainReq(BaseModel):
    question: str = ""
    locale: str = "en"
    
@router.post("/structures/{structure_id}/explain")
def explain(structure_id: str, req: ExplainReq, db=Depends(get_db), graph=Depends(get_anatomy_graph)):
    guard = check_input(req.question)
    if not guard.allowed:
        return {"text": guard.redirect, "citations": [], "grounded": False}
    e = explain_structure(structure_id, req.question, req.locale, db, graph)
    return {"text": e.text, "citations": e.citations, "grounded": e.grounded}


@router.post("/tutor/ask")
async def ask(req: ExplainReq, structure_id: str, db=Depends(get_db), graph=Depends(get_anatomy_graph)):
    guard = check_input(req.question)
    async def gen():
        if not guard.allowed:
            yield {"data": json.dumps({"token": guard.redirect})}
            yield {"data": json.dumps({"done": True, "citations": [], "grounded": False})}
            return
        e = await run_in_threadpool(explain_structure, structure_id, req.question, req.locale, db, graph)
        for token in e.text.split(" "):
            yield {"data": json.dumps({"token": token + " "})}
        yield {"data": json.dumps({"done": True, "citations": e.citations, "grounded": e.grounded})}
    return EventSourceResponse(gen())