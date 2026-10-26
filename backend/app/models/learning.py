from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lesson_id: Mapped[str] = mapped_column(String)
    structure_id: Mapped[str] = mapped_column(String)
    difficulty: Mapped[str] = mapped_column(String)
    prompt: Mapped[str] = mapped_column(String)
    correct: Mapped[str] = mapped_column(String)
    choices: Mapped[list] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String, default="DRAFT")

class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String)
    question_id: Mapped[str] = mapped_column(ForeignKey("quiz_questions.id"))
    correct: Mapped[bool] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Progress(Base):
    __tablename__ = "progress"
    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    structure_id: Mapped[str] = mapped_column(String, primary_key=True)
    mastery: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

class BanditEvent(Base):
    __tablename__ = "bandit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)
    context_json: Mapped[dict] = mapped_column(JSON)
    reward: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class DpoPreference(Base):
    __tablename__ = "dpo_preferences"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    prompt: Mapped[str] = mapped_column(Text)
    chosen: Mapped[str] = mapped_column(Text)
    rejected: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, default="judge")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
