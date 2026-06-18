from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models.user import User
from app.api import (
    auth,
    cdl,
    departments,
    evaluation,
    local_documents,
    results,
    scrape_departments,
    scrape_stream,
    stats,
    syllabi,
)


def _ensure_sqlite_schema_compatibility() -> None:
    """Add lightweight SQLite columns introduced after initial local DB creation."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "syllabi" not in table_names:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("syllabi")}
    columns_to_add = {
        "learning_outcomes_it": "TEXT NOT NULL DEFAULT ''",
        "learning_outcomes_en": "TEXT",
        # ISSUE-PARSER-004 (Phase 5.4.K): bilingual course title.
        "course_name_en": "TEXT",
    }

    with engine.begin() as conn:
        for column_name, ddl in columns_to_add.items():
            if column_name not in existing_columns:
                conn.execute(text(f"ALTER TABLE syllabi ADD COLUMN {column_name} {ddl}"))

    # Phase 9.C.5.3: add ``extended_criteria_result`` JSON column to
    # ``evaluation_results`` if absent. We can't drop+recreate that
    # table any more — it now holds real run history — and Alembic
    # is intentionally out of scope (D020), so an idempotent ALTER
    # at startup is the smallest viable migration.
    if "evaluation_results" in table_names:
        eval_columns = {
            c["name"] for c in inspector.get_columns("evaluation_results")
        }
        with engine.begin() as conn:
            if "extended_criteria_result" not in eval_columns:
                conn.execute(
                    text(
                        "ALTER TABLE evaluation_results "
                        "ADD COLUMN extended_criteria_result JSON",
                    ),
                )


def _ensure_auth_admin_bootstrap() -> None:
    """Guarantee one admin for local/prototype installations.

    Phase 11.D introduces admin-only account management. Fresh
    installs get an admin through "first registered user wins"; this
    compatibility hook protects already-created local DBs that may
    contain only ``quality_reviewer`` users from Phase 11.A-C.
    """
    db = SessionLocal()
    try:
        has_admin = (
            db.query(User)
            .filter(User.role == "admin")
            .filter(User.is_active.is_(True))
            .first()
            is not None
        )
        if has_admin:
            return
        first_active_user = (
            db.query(User)
            .filter(User.is_active.is_(True))
            .order_by(User.created_at.asc(), User.id.asc())
            .first()
        )
        if first_active_user is None:
            return
        first_active_user.role = "admin"
        db.commit()
    finally:
        db.close()


def _ensure_evaluation_results_schema() -> None:
    """Drop+recreate ``evaluation_results`` when the stub schema is detected.

    Until Phase 5.4.H the table carried only ``model_name`` / ``status`` /
    ``score_overall`` / ``report_json`` / ``evaluated_at``. The full
    Appendix C schema introduces ~25 new columns. Since the legacy
    table never held real records (the stub was never written to),
    drop+recreate is safe and simpler than a column-by-column ALTER
    (D020 keeps Alembic out of scope for the thesis prototype).

    Detection key: presence of ``evaluation_uuid`` column. If absent,
    drop the table and let ``Base.metadata.create_all`` recreate it
    with the full schema.
    """
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "evaluation_results" not in inspector.get_table_names():
        return
    existing_columns = {c["name"] for c in inspector.get_columns("evaluation_results")}
    if "evaluation_uuid" in existing_columns:
        return  # already on the new schema
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE evaluation_results"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema migrations BEFORE create_all so dropped tables are recreated.
    _ensure_evaluation_results_schema()
    Base.metadata.create_all(engine)
    _ensure_auth_admin_bootstrap()
    _ensure_sqlite_schema_compatibility()
    yield


app = FastAPI(
    title="Syllabus Quality Assurance API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_AUTHENTICATED_API = [Depends(auth.current_user)]

app.include_router(auth.router)
app.include_router(departments.router, dependencies=_AUTHENTICATED_API)
app.include_router(scrape_departments.router, dependencies=_AUTHENTICATED_API)
app.include_router(scrape_stream.router, dependencies=_AUTHENTICATED_API)
app.include_router(evaluation.router, dependencies=_AUTHENTICATED_API)
app.include_router(results.router, dependencies=_AUTHENTICATED_API)
app.include_router(cdl.router, dependencies=_AUTHENTICATED_API)
app.include_router(syllabi.router, dependencies=_AUTHENTICATED_API)
app.include_router(stats.router, dependencies=_AUTHENTICATED_API)
app.include_router(local_documents.router, dependencies=_AUTHENTICATED_API)
