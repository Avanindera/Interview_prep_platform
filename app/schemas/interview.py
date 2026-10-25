from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class InterviewCreate(BaseModel):
    subject_id: int
    topic_id: Optional[int] = None


class AnswerSubmit(BaseModel):
    answer_text: str


class AnswerResponse(BaseModel):
    id: int
    interview_question_id: int
    answer_text: str
    submitted_at: datetime

    class Config:
        from_attributes = True


class InterviewQuestionResponse(BaseModel):
    id: int
    question_id: int
    order: int
    question_text: str
    difficulty: str
    is_answered: bool = False
    answer: Optional[AnswerResponse] = None

    class Config:
        from_attributes = True


class InterviewResponse(BaseModel):
    id: int
    user_id: int
    subject_id: int
    subject_name: Optional[str] = None
    topic_id: Optional[int] = None
    topic_name: Optional[str] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    current_question_number: int

    class Config:
        from_attributes = True


class InterviewDetailResponse(InterviewResponse):
    questions: List[InterviewQuestionResponse] = []

