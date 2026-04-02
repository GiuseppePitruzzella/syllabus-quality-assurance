from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    syllabus_id: Mapped[int] = mapped_column(Integer, ForeignKey("syllabi.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    score_overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    syllabus = relationship("Syllabus", back_populates="evaluations")
