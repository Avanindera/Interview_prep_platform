from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ResumeResponse(BaseModel):
    id: int
    user_id: int
    filename: str
    file_size: int
    content_type: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True

