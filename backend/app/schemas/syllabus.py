from datetime import datetime

from pydantic import BaseModel


class SyllabusListItem(BaseModel):
    """Lightweight schema for syllabus list views (no content fields)."""

    id: int
    cdl_id: int
    seuid: str
    course_code: str
    course_name: str
    module: str | None
    teacher: str
    academic_year: str
    year_of_study: str
    url_it: str
    url_en: str
    has_english: bool
    scraped_at: datetime

    model_config = {"from_attributes": True}


class SyllabusDetail(SyllabusListItem):
    """Full schema with all content fields — used for GET /api/syllabi/{seuid}."""

    dublin_knowledge_it: str | None = None
    dublin_applying_it: str | None = None
    dublin_judgement_it: str | None = None
    dublin_communication_it: str | None = None
    dublin_learning_it: str | None = None
    teaching_methods_it: str | None = None
    prerequisites_it: str | None = None
    attendance_it: str | None = None
    course_content_it: str | None = None
    references_it: str | None = None
    schedule_it: list | None = None
    assessment_methods_it: str | None = None
    sample_questions_it: str | None = None
    dublin_knowledge_en: str | None = None
    dublin_applying_en: str | None = None
    dublin_judgement_en: str | None = None
    dublin_communication_en: str | None = None
    dublin_learning_en: str | None = None
    teaching_methods_en: str | None = None
    prerequisites_en: str | None = None
    attendance_en: str | None = None
    course_content_en: str | None = None
    references_en: str | None = None
    schedule_en: list | None = None
    assessment_methods_en: str | None = None
    sample_questions_en: str | None = None

    # Breadcrumb fields (resolved via relationships)
    cdl_name: str | None = None
    department_id: int | None = None
    department_name: str | None = None
