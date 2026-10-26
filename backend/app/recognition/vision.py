import io
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from app.models.content import Page
from app.recognition import embedder

def embed_image(image_bytes: bytes) -> list[float]:
    img = embedder.open_image(image_bytes)
    if img is None:
        raise ValueError("unreadable image")
    return embedder.embed_image(img)

def search_pages_by_embedding(vec: list[float], db, k: int = 3) -> list[tuple[Page, float]]:
    dist = Page.embedding.cosine_distance(vec).label("dist")
    rows = db.execute(select(Page, dist).order_by(dist).limit(k)).all()
    return [(p, 1.0 - float(d)) for p, d in rows]

def ocr_labels(image_bytes: bytes) -> list[str]:
    try:
        import pytesseract
        text = pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes)))
    except (ImportError, UnidentifiedImageError, OSError): 
        return []
    return [ln.strip() for ln in text.splitlines() if len(ln.strip()) >= 3]
