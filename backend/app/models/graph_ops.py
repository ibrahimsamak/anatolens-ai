from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class EdgeProposal(Base):
    __tablename__ = "edge_proposals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lesson_id: Mapped[str] = mapped_column(String, index=True)
    subject_id: Mapped[str] = mapped_column(String)
    predicate: Mapped[str] = mapped_column(String)
    object_id: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="AI_GENERATED", index=True)
    conflict: Mapped[bool] = mapped_column(Boolean, default=False)

    def __init__(self, **kw):
        kw.setdefault("confidence", 0.0)
        kw.setdefault("status", "AI_GENERATED")
        kw.setdefault("conflict", False)
        super().__init__(**kw)


class MeshCandidate(Base):
    __tablename__ = "mesh_candidates"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lesson_id: Mapped[str] = mapped_column(String, index=True)
    glb_path: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="AI_GENERATED", index=True)
    reason: Mapped[str] = mapped_column(String, default="")

    def __init__(self, **kw):
        kw.setdefault("status", "AI_GENERATED")
        kw.setdefault("reason", "")
        super().__init__(**kw)
