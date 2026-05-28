from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Syllabus(Base):
    __tablename__ = "syllabi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cdl_id: Mapped[int] = mapped_column(Integer, ForeignKey("corsi_di_laurea.id", ondelete="CASCADE"), nullable=False)
    seuid: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    course_code: Mapped[str] = mapped_column(Text, nullable=False)
    course_name: Mapped[str] = mapped_column(Text, nullable=False)
    # English variant of the course title, scraped from the EN detail
    # page (ISSUE-PARSER-004). Nullable because not every syllabus has
    # an EN version, and pre-5.4.K rows do not have it populated. When
    # absent the UI / agents should fall back to ``course_name``.
    course_name_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    module: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher: Mapped[str] = mapped_column(Text, nullable=False)
    academic_year: Mapped[str] = mapped_column(Text, nullable=False)
    year_of_study: Mapped[str] = mapped_column(Text, nullable=False)
    url_it: Mapped[str] = mapped_column(Text, nullable=False)
    url_en: Mapped[str] = mapped_column(Text, nullable=False)
    has_english: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Learning outcomes and Dublin Descriptors — Italian
    learning_outcomes_it: Mapped[str] = mapped_column(Text, nullable=False)
    dublin_knowledge_it: Mapped[str] = mapped_column(Text, nullable=False)
    dublin_applying_it: Mapped[str] = mapped_column(Text, nullable=False)
    dublin_judgement_it: Mapped[str] = mapped_column(Text, nullable=False)
    dublin_communication_it: Mapped[str] = mapped_column(Text, nullable=False)
    dublin_learning_it: Mapped[str] = mapped_column(Text, nullable=False)

    # Sections — Italian
    teaching_methods_it: Mapped[str] = mapped_column(Text, nullable=False)
    prerequisites_it: Mapped[str] = mapped_column(Text, nullable=False)
    attendance_it: Mapped[str] = mapped_column(Text, nullable=False)
    course_content_it: Mapped[str] = mapped_column(Text, nullable=False)
    references_it: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_it: Mapped[list | None] = mapped_column(JSON, nullable=True)
    assessment_methods_it: Mapped[str] = mapped_column(Text, nullable=False)
    sample_questions_it: Mapped[str] = mapped_column(Text, nullable=False)

    # Learning outcomes and Dublin Descriptors — English
    learning_outcomes_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    dublin_knowledge_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    dublin_applying_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    dublin_judgement_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    dublin_communication_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    dublin_learning_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Sections — English
    teaching_methods_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    prerequisites_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    attendance_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    course_content_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    references_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_en: Mapped[list | None] = mapped_column(JSON, nullable=True)
    assessment_methods_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_questions_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    cdl = relationship("CorsoDiLaurea", back_populates="syllabi")
    evaluations = relationship("EvaluationResult", back_populates="syllabus", cascade="all, delete-orphan")
