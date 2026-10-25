import io
from functools import lru_cache
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from app.core.config import settings

def open_image(image_bytes: bytes) -> Image.Image | None:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except (UnidentifiedImageError, OSError):
        return None
    return ImageOps.exif_transpose(img).convert("RGB")

@lru_cache(maxsize=1)
def _model():
    from fastembed import ImageEmbedding
    return ImageEmbedding(settings.recognition_model)

def embed_image(img: Image.Image) -> list[float]:
    v = next(iter(_model().embed([img])))
    return (v / np.linalg.norm(v)).tolist()

TEMPLATES = ["an anatomical illustration of {}", "a medical diagram of {}", "a 3D model of {}", "a textbook figure of {}"]
BACKGROUND = ["a page of text", "a photo", "a person", "an animal", "a room", "an object", "a blank sheet of paper", "random noise", "the human brain", "the lungs", "a human skeleton", "a hand", "a drawing", "a chart or diagram"]

@lru_cache(maxsize=1)
def _clip():
    from fastembed import ImageEmbedding, TextEmbedding
    return ImageEmbedding(f"{settings.recognition_semantic_model}-vision"), TextEmbedding(f"{settings.recognition_semantic_model}-text")

def _unit(a: np.ndarray) -> np.ndarray:
    return a / np.linalg.norm(a, axis=-1, keepdims=True)

@lru_cache(maxsize=256)
def _class_vector(subject: str) -> np.ndarray:
    return _unit(_unit(np.array(list(_clip()[1].embed([t.format(subject) for t in TEMPLATES])))).mean(0))

def classify(img: Image.Image, subjects: dict[str, str]) -> list[tuple[str, float]]:
    if not subjects:
        return []
    classes = np.array([_class_vector(s) for s in [*subjects.values(), *BACKGROUND]])
    logits = 100 * _unit(next(iter(_clip()[0].embed([img])))) @ classes.T
    p = np.exp(logits - logits.max()); p /= p.sum()
    return sorted(zip(subjects, p[:len(subjects)].tolist()), key=lambda x: -x[1])
