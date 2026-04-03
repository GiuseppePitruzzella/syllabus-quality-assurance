from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.api import departments, scrape_departments, scrape_stream, evaluation, cdl


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Syllabus Quality Assurance API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(departments.router)
app.include_router(scrape_departments.router)
app.include_router(scrape_stream.router)
app.include_router(evaluation.router)
app.include_router(cdl.router)
