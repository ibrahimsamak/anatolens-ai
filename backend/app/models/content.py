from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.models.base import Base

class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    system: Mapped[str] = mapped_column(String)
    model_url: Mapped[str] = mapped_column(String)
    ios_model_url: Mapped[str | None] = mapped_column(String, nullable=True)
    review_status: Mapped[str] = mapped_column(String, default="DRAFT")

class Structure(Base):
    __tablename__ = "structures"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"))
    mesh_name: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name_en: Mapped[str] = mapped_column(String)
    display_name_ar: Mapped[str | None] = mapped_column(String, nullable=True)

class Page(Base):
    __tablename__ = "pages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"))
    phash: Mapped[str] = mapped_column(String)
    embedding: Mapped[list[float]] = mapped_column(Vector(512))

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"))
    structure_id: Mapped[str | None] = mapped_column(String, nullable=True)
    locale: Mapped[str] = mapped_column(String, default="en")
    text: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String, default="DRAFT")
    source: Mapped[str] = mapped_column(String, default="")
    source_version: Mapped[str] = mapped_column(String, default="")
    reviewer: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))

class ScanSession(Base):
    __tablename__ = "scan_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lesson_id: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
