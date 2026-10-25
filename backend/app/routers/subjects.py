from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.subject import Subject, Topic
from app.schemas.subject import SubjectResponse, SubjectDetailResponse, TopicResponse

router = APIRouter(prefix="/subjects", tags=["Subjects & Topics"])


@router.get("", response_model=List[SubjectResponse])
def get_subjects(db: Session = Depends(get_db)):
    subjects = db.query(Subject).all()
    return subjects


@router.get("/{subject_id}", response_model=SubjectDetailResponse)
def get_subject_detail(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    return subject


@router.get("/{subject_id}/topics", response_model=List[TopicResponse])
def get_subject_topics(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    topics = db.query(Topic).filter(Topic.subject_id == subject_id).all()
    return topics

