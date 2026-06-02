from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.department import Department
from app.models.cdl import CorsoDiLaurea
from app.models.syllabus import Syllabus


def test_create_department(db_session):
    dept = Department(
        name="Matematica e Informatica",
        area="Area scientifica",
        website_url="https://web.dmi.unict.it",
        email="dipartimento@dmi.unict.it",
        phone="+39 095 123 4567",
        director="Mario Rossi",
        scraped_at=datetime.now(timezone.utc),
    )
    db_session.add(dept)
    db_session.commit()

    result = db_session.query(Department).first()
    assert result is not None
    assert result.name == "Matematica e Informatica"
    assert result.area == "Area scientifica"
    assert result.website_url == "https://web.dmi.unict.it"


def test_department_cdl_relationship(db_session):
    dept = Department(
        name="Matematica e Informatica",
        area="Area scientifica",
        website_url="https://web.dmi.unict.it",
        email="dipartimento@dmi.unict.it",
        phone="+39 095 123 4567",
        director="Mario Rossi",
        scraped_at=datetime.now(timezone.utc),
    )
    db_session.add(dept)
    db_session.flush()

    cdl = CorsoDiLaurea(
        department_id=dept.id,
        name="Informatica",
        code="lm-18",
        type="Magistrale",
        academic_year="2025/2026",
        url="https://web.dmi.unict.it/corsi/lm-18",
        scraped_at=datetime.now(timezone.utc),
    )
    db_session.add(cdl)
    db_session.commit()

    result = db_session.query(Department).first()
    assert len(result.cdl_list) == 1
    assert result.cdl_list[0].name == "Informatica"
    assert result.cdl_list[0].academic_year == "2025/2026"


def test_syllabus_seuid_unique(db_session):
    dept = Department(
        name="DMI", area="Scientifica", website_url="https://web.dmi.unict.it",
        email="x@x.it", phone="000", director="X", scraped_at=datetime.now(timezone.utc),
    )
    db_session.add(dept)
    db_session.flush()

    cdl = CorsoDiLaurea(
        department_id=dept.id, name="Informatica", code="lm-18", type="Magistrale",
        url="https://web.dmi.unict.it/corsi/lm-18", scraped_at=datetime.now(timezone.utc),
    )
    db_session.add(cdl)
    db_session.flush()

    common = dict(
        cdl_id=cdl.id, seuid="ABC-123", course_code="001", course_name="Test",
        teacher="Prof X", academic_year="2025/2026", year_of_study="1",
        url_it="http://a", url_en="http://b",
        learning_outcomes_it="",
        dublin_knowledge_it="", dublin_applying_it="", dublin_judgement_it="",
        dublin_communication_it="", dublin_learning_it="",
        teaching_methods_it="", prerequisites_it="", attendance_it="",
        course_content_it="", references_it="", assessment_methods_it="",
        sample_questions_it="", scraped_at=datetime.now(timezone.utc),
    )

    db_session.add(Syllabus(**common))
    db_session.commit()

    db_session.add(Syllabus(**common))
    with pytest.raises(IntegrityError):
        db_session.commit()
