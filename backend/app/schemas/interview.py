from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class InterviewCreate(BaseModel):
    subject_id: Optional[int] = None
    topic_id: Optional[int] = None
    generation_mode: Optional[str] = "CURATED"  # "CURATED" or "RAG_DYNAMIC"
    custom_topic: Optional[str] = None
    question_count: Optional[int] = 3


class AnswerSubmit(BaseModel):
    answer_text: Optional[str] = ""


class FollowUpSubmit(BaseModel):
    follow_up_answer: str


class AnswerResponse(BaseModel):
    id: int
    interview_question_id: int
    answer_text: str
    audio_path: Optional[str] = None
    submitted_at: datetime

    # Technical Evaluation
    technical_score: Optional[float] = None
    technical_verdict: Optional[str] = None
    technical_feedback: Optional[str] = None
    misconception: Optional[str] = None
    follow_up_question: Optional[str] = None
    follow_up_answer: Optional[str] = None
    follow_up_feedback: Optional[str] = None

    # Speech Delivery Evaluation
    speech_verdict: Optional[str] = None
    speech_confidence: Optional[float] = None
    filler_count: Optional[int] = None
    filler_density: Optional[float] = None
    hedging_count: Optional[int] = None
    technical_keyword_count: Optional[int] = None
    technical_density: Optional[float] = None
    lexical_diversity: Optional[float] = None
    speech_feedback: Optional[str] = None

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
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    topic_id: Optional[int] = None
    topic_name: Optional[str] = None
    generation_mode: str = "CURATED"
    custom_topic: Optional[str] = None
    overall_score: Optional[float] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    current_question_number: int

    class Config:
        from_attributes = True


class InterviewDetailResponse(InterviewResponse):
    questions: List[InterviewQuestionResponse] = []
