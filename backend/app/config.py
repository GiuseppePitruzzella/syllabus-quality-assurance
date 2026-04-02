from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{Path(__file__).resolve().parent.parent / 'data' / 'syllabus_ai.db'}"
    scrape_delay: float = 1.5
    scrape_timeout: int = 15
    scrape_user_agent: str = "SyllabusAI/1.0 (UniCT research thesis)"


settings = Settings()
