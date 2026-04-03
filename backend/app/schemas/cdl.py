from datetime import datetime

from pydantic import BaseModel


class CdLResponse(BaseModel):
    id: int
    department_id: int
    name: str
    code: str
    type: str
    academic_year: str | None
    url: str
    scraped_at: datetime

    model_config = {"from_attributes": True}
