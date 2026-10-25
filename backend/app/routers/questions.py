from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.interview import Question

router = APIRouter(prefix="/questions", tags=["Questions"])


class QuestionBankItem(BaseModel):
    id: int
    subject_id: int
    topic_id: Optional[int] = None
    question_text: str
    difficulty: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[QuestionBankItem])
def get_questions(
    subject_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Question)
    if subject_id is not None:
        query = query.filter(Question.subject_id == subject_id)
    if topic_id is not None:
        query = query.filter(Question.topic_id == topic_id)
    return query.all()

