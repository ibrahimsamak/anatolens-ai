import io
import uuid
from pathlib import Path
from typing import Literal
import yaml
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import select
from langgraph.types import Command
from app.api.deps import CONTENT, get_db, require_role, get_authoring_graph, get_anatomy_graph
from app.cv.proposals import save_proposals
from app.cv.relations import extract_relations
from app.cv.segmentation import segment_regions, regions_to_structure_ids
from app.models.content import Lesson, Structure
from app.models.graph_ops import EdgeProposal, MeshCandidate
from app.models.review import ReviewTask
from app.models.user import User
from app.rag.graphrag import get_cache
from app.recon.pipeline import reconstruct
from app.recon.review import can_approve_mesh
from app.recon.validate import validate_mesh
from app.services.review import advance, can_perform, EDITORS, REVIEWERS

router = APIRouter(prefix="/api/v1/admin")
STAFF = ("CONTENT_EDITOR", "MEDICAL_REVIEWER", "SUPER_ADMIN")
PENDING = ("AI_GENERATED", "CONTENT_REVIEW", "MEDICAL_REVIEW")


class LessonReq(BaseModel):
    id: str
    title: str
    system: str
    model_url: str
    ios_model_url: str | None = None

class TransitionReq(BaseModel): action: str

class ReviewReq(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str = ""

def lesson_info(l: Lesson):
    return {"id": l.id, "title": l.title, "system": l.system, "review_status": l.review_status}


def task_info(t: ReviewTask):
    return {
        "thread_id": t.thread_id,
        "lesson_id": t.lesson_id,
        "structure_id": t.structure_id,
        "status": t.status,
        "draft_text": t.draft_text,
        "created_by": t.created_by,
        "reviewer": t.reviewer,
        "notes": t.notes,
        "updated_at": t.updated_at.isoformat(),
    }


def email_of(db, user):
    u = db.get(User, user["sub"])
    return u.email if u else user["sub"]


@router.get("/lessons", dependencies=[Depends(require_role(*STAFF))])
def list_lessons(db=Depends(get_db)):
    lessons = db.execute(select(Lesson).order_by(Lesson.title)).scalars()
    return [lesson_info(l) for l in lessons]


@router.post("/lessons", status_code=201, dependencies=[Depends(require_role(*EDITORS))])
def create_lesson(req: LessonReq, db=Depends(get_db)):
    if db.get(Lesson, req.id):
        raise HTTPException(409, "lesson already exists")
    lesson = Lesson(**req.model_dump(), review_status="DRAFT")
    db.add(lesson)
    db.commit()
    return lesson_info(lesson)


@router.post("/lessons/{lesson_id}/transition")
def transition(lesson_id: str, req: TransitionReq, user=Depends(require_role(*STAFF)), db=Depends(get_db)):
    if not can_perform(user["role"], req.action):
        raise HTTPException(403, f"{user['role']} cannot {req.action}")
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "unknown lesson")
    try:
        lesson.review_status = advance(lesson.review_status, req.action)
    except ValueError as e:
        raise HTTPException(409, str(e))
    db.commit()
    return lesson_info(lesson)


@router.post("/lessons/{lesson_id}/author", status_code=201)
def author(lesson_id: str, structure_id: str, user=Depends(require_role(*EDITORS)), db=Depends(get_db), graph=Depends(get_authoring_graph)):
    structure = db.get(Structure, structure_id)
    if not structure or structure.lesson_id != lesson_id:
        raise HTTPException(404, "unknown structure for this lesson")

    thread_id = f"{lesson_id}:{structure_id}:{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    out = graph.invoke({"lesson_id": lesson_id, "structure_id": structure_id, "structure_name": structure.display_name_en}, config)

    task = ReviewTask(thread_id=thread_id, lesson_id=lesson_id, structure_id=structure_id, status=out["status"], draft_text=out.get("draft_text", ""), created_by=email_of(db, user))
    db.add(task)
    db.commit()

    result = task_info(task)
    result["interrupted"] = "__interrupt__" in out
    return result


@router.get("/reviews", dependencies=[Depends(require_role(*STAFF))])
def list_reviews(status: str = "MEDICAL_REVIEW", db=Depends(get_db)):
    query = select(ReviewTask).order_by(ReviewTask.updated_at.desc())
    if status:
        query = query.where(ReviewTask.status == status)
    return [task_info(t) for t in db.execute(query).scalars()]


@router.post("/review/{thread_id}")
def review(thread_id: str, req: ReviewReq, user=Depends(require_role(*REVIEWERS)), db=Depends(get_db), graph=Depends(get_authoring_graph)):
    task = db.get(ReviewTask, thread_id)
    if not task:
        raise HTTPException(404, "unknown review")

    config = {"configurable": {"thread_id": thread_id}}
    if task.status != "MEDICAL_REVIEW" or not graph.get_state(config).interrupts:
        raise HTTPException(409, f"review is not awaiting a decision (status {task.status})")

    reviewer = email_of(db, user)
    answer = {"decision": req.decision, "reviewer": reviewer, "notes": req.notes}
    final = graph.invoke(Command(resume=answer), config)

    task.status = final["status"]
    task.reviewer = reviewer
    task.notes = req.notes or None
    db.commit()

    result = task_info(task)
    result["chunk_id"] = final.get("chunk_id") or None
    return result


def proposal_info(p: EdgeProposal):
    return {"id": p.id, "lesson_id": p.lesson_id, "subject_id": p.subject_id, "predicate": p.predicate,
            "object_id": p.object_id, "confidence": p.confidence, "status": p.status, "conflict": p.conflict}


def mesh_info(m: MeshCandidate):
    return {"id": m.id, "lesson_id": m.lesson_id, "glb_path": m.glb_path, "url": f"/assets/{Path(m.glb_path).name}",
            "status": m.status, "reason": m.reason}


def pending(db, model, item_id):
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(404, "not found")
    if item.status not in PENDING:
        raise HTTPException(409, f"not awaiting a decision (status {item.status})")
    return item


def lesson_pack(lesson_id):
    for f in CONTENT.glob("*/lesson.yaml"):
        if (yaml.safe_load(f.read_text("utf-8")) or {}).get("id") == lesson_id:
            return f.parent
    return None


@router.post("/lessons/{lesson_id}/analyze", status_code=201, dependencies=[Depends(require_role(*EDITORS))])
def analyze_diagram(lesson_id: str, file: UploadFile = File(...), make_3d: bool = False, db=Depends(get_db), graph=Depends(get_anatomy_graph)):
    pack = lesson_pack(lesson_id)
    if not pack or not db.get(Lesson, lesson_id):
        raise HTTPException(404, "unknown lesson")
    image = file.file.read()
    try:
        Image.open(io.BytesIO(image)).verify()
    except Exception:
        raise HTTPException(400, "not an image")

    structures = str(pack / "structures.yaml")
    result = {"regions": [], "proposals": [], "known": [], "mesh": None, "notes": []}

    try:
        regions = segment_regions(image)
        for region, sid in regions_to_structure_ids(regions, structures):
            result["regions"].append({"label": region.ocr_label, "structure_id": sid})
    except Exception as e:
        result["notes"].append(f"segmentation skipped: {e}")

    try:
        proposals = extract_relations(image, lesson_id, structures)
        new = [p for p in proposals if p.object_id not in graph.objects(p.subject_id, p.predicate)]
        save_proposals(new, graph, db)
        result["proposals"] = [proposal_info(p) for p in new]
        result["known"] = [{"subject_id": p.subject_id, "predicate": p.predicate, "object_id": p.object_id}
                           for p in proposals if p not in new]
    except Exception as e:
        result["notes"].append(f"relation extraction failed: {e}")

    if make_3d:
        try:
            mesh = reconstruct(image, str(pack / "assets" / f"ai_{uuid.uuid4().hex[:8]}.glb"), lesson_id)
            db.add(mesh)
            db.commit()
            result["mesh"] = mesh_info(mesh)
        except Exception as e:
            result["notes"].append(f"3D skipped: {e}")

    return result


@router.get("/proposals", dependencies=[Depends(require_role(*STAFF))])
def list_proposals(status: str = "AI_GENERATED", db=Depends(get_db)):
    query = select(EdgeProposal).order_by(EdgeProposal.conflict.desc(), EdgeProposal.confidence.desc())
    if status:
        query = query.where(EdgeProposal.status == status)
    return [proposal_info(p) for p in db.execute(query).scalars()]


@router.post("/proposals/{proposal_id}/{decision}", dependencies=[Depends(require_role(*REVIEWERS))])
def decide_proposal(proposal_id: str, decision: Literal["approve", "reject"], db=Depends(get_db),
                    graph=Depends(get_anatomy_graph)):
    p = pending(db, EdgeProposal, proposal_id)
    if decision == "reject":
        p.status = "DRAFT"
        db.commit()
        return proposal_info(p)

    graph.add_edge(p.subject_id, p.predicate, p.object_id)
    p.status = "APPROVED"
    db.commit()
    if cache := get_cache():
        cache.clear([p.subject_id, p.object_id])
    return proposal_info(p)


@router.get("/meshes", dependencies=[Depends(require_role(*STAFF))])
def list_meshes(status: str = "AI_GENERATED", db=Depends(get_db)):
    query = select(MeshCandidate)
    if status:
        query = query.where(MeshCandidate.status == status)
    return [mesh_info(m) for m in db.execute(query).scalars()]


@router.post("/meshes/{mesh_id}/reject", dependencies=[Depends(require_role(*REVIEWERS))])
def reject_mesh(mesh_id: str, db=Depends(get_db)):
    m = pending(db, MeshCandidate, mesh_id)
    m.status = "DRAFT"
    m.reason = "rejected by reviewer"
    db.commit()
    return mesh_info(m)


@router.post("/meshes/{mesh_id}/approve", dependencies=[Depends(require_role(*REVIEWERS))])
def approve_mesh(mesh_id: str, db=Depends(get_db)):
    m = pending(db, MeshCandidate, mesh_id)
    lesson = db.get(Lesson, m.lesson_id)
    if not lesson:
        raise HTTPException(404, "unknown lesson")

    ok, reason = validate_mesh(m.glb_path)
    if not ok:
        raise HTTPException(409, reason)

    structures = db.execute(select(Structure).where(Structure.lesson_id == m.lesson_id,
                                                    Structure.mesh_name.is_not(None))).scalars().all()
    ok, missing = can_approve_mesh(m.glb_path, [s.id for s in structures], {s.id: s.mesh_name for s in structures})
    if not ok:
        raise HTTPException(409, {"detail": "GLB is missing named meshes", "missing": missing})

    m.status = "APPROVED"
    lesson.model_url = f"/assets/{Path(m.glb_path).name}"
    db.commit()
    return mesh_info(m)
