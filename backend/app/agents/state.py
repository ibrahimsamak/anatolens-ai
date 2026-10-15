from typing import TypedDict, Optional

class TutorState(TypedDict, total=False):
    image_bytes: bytes
    lesson_id: Optional[str]
    confidence: float
    active_structure_id: Optional[str]
    question: str
    locale: str
    answer: str
    citations: list[str]
    grounded: bool
    decision: str
