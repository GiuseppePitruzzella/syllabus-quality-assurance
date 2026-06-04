from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, engine
from app.api import (
    cdl,
    departments,
    evaluation,
    local_documents,
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(departments.router)
app.include_router(scrape_departments.router)
app.include_router(scrape_stream.router)
app.include_router(evaluation.router)
app.include_router(cdl.router)
app.include_router(syllabi.router)
app.include_router(stats.router)
app.include_router(local_documents.router)
