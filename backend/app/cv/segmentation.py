import io
from dataclasses import dataclass
from functools import lru_cache
from PIL import Image
from app.recognition.vision import ocr_labels
from app.recognition.ontology import OntologyResolver


@dataclass
class Region:
    bbox: tuple
    mask_area: int
    ocr_label: str | None


@lru_cache
def _model():
    from ultralytics import YOLO
    return YOLO("yolov8n-seg.pt")


def segment_regions(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    res = _model()(img, verbose=False)[0]
    masks = res.masks.data if res.masks is not None else None
    regions = []
    for i, box in enumerate(res.boxes or []):
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        x1, y1, x2, y2 = max(x1, 0), max(y1, 0), min(x2, img.width), min(y2, img.height)
        if x2 <= x1 or y2 <= y1:
            continue
        buf = io.BytesIO()
        img.crop((x1, y1, x2, y2)).save(buf, format="PNG")
        labels = ocr_labels(buf.getvalue())
        area = int(masks[i].sum()) if masks is not None else (x2 - x1) * (y2 - y1)
        regions.append(Region((x1, y1, x2, y2), area, labels[0] if labels else None))
    return regions


def regions_to_structure_ids(regions, structures_yaml_path):
    resolver = OntologyResolver.from_yaml(structures_yaml_path)
    return [(r, resolver.resolve_fuzzy(r.ocr_label) if r.ocr_label else None) for r in regions]
