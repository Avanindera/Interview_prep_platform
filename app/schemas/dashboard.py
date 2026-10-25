from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class RecentInterviewItem(BaseModel):
    id: int
    subject: str
    topic: Optional[str] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    total_interviews: int
    completed_interviews: int
    in_progress_interviews: int
    questions_answered: int
    recent_interviews: List[RecentInterviewItem] = []

