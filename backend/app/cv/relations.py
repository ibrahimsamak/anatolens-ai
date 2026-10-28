import base64, io, uuid
import yaml
from PIL import Image
from app.llm.factory import get_vision_model
from app.recognition.ontology import OntologyResolver
from app.models.graph_ops import EdgeProposal
from app.schemas.relations import DiagramRelations

PROMPT = """This is an anatomy diagram. The lesson only knows these structures:
{structures}

Map every label in the diagram to one structure from the list. A label for a part of a listed structure
maps to that structure (for example "Fundus" or "Pylorus" -> the stomach, "Superior part of duodenum" -> the duodenum).
Skip labels that match nothing in the list.

Then list the relationships between the mapped structures that the diagram shows and that are anatomically correct:
- "connects_to": the two structures are directly joined (content or tissue passes from one to the other)
- "part_of": the subject is a part of the object

Use only ids from the list and never link a structure to itself."""


def image_url(image_bytes):
    try:
        mime = Image.open(io.BytesIO(image_bytes)).get_format_mimetype()
    except Exception:
        mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"


def extract_relations(image_bytes, lesson_id, structures_yaml_path):
    with open(structures_yaml_path, encoding="utf-8") as f:
        structures = "\n".join(f"- {s['id']}: {s['display_name_en']}" for s in yaml.safe_load(f) or [])
    reply = get_vision_model().with_structured_output(DiagramRelations).invoke([{"role": "user", "content": [
        {"type": "text", "text": PROMPT.format(structures=structures)},
        {"type": "image_url", "image_url": {"url": image_url(image_bytes)}}]}])

    resolver = OntologyResolver.from_yaml(structures_yaml_path)
    found = {}
    for r in reply.relations:
        s, o = resolver.resolve_fuzzy(r.subject), resolver.resolve_fuzzy(r.object)
        if s and o and s != o:
            found.setdefault((s, r.predicate, o), None)
    return [EdgeProposal(id=str(uuid.uuid4()), lesson_id=lesson_id, subject_id=s, predicate=p, object_id=o, confidence=0.6)
            for s, p, o in found]
