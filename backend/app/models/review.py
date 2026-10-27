from datetime import datetime
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class ReviewTask(Base):
    __tablename__ = "review_tasks"
    thread_id: Mapped[str] = mapped_column(String, primary_key=True)
    lesson_id: Mapped[str] = mapped_column(String, index=True)
    structure_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    draft_text: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String)
    reviewer: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
