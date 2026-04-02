from datetime import datetime
from pydantic import BaseModel


class DepartmentResponse(BaseModel):
    id: int
    name: str
    area: str
    website_url: str
    email: str
    phone: str
    director: str
    scraped_at: datetime

    model_config = {"from_attributes": True}
