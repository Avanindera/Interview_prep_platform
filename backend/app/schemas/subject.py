from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class TopicResponse(BaseModel):
    id: int
    subject_id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SubjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SubjectDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    topics: List[TopicResponse] = []

    class Config:
        from_attributes = True

