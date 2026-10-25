from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.models.subject import Subject, Topic
from app.models.interview import InterviewSession, Question, InterviewQuestion, Answer
from app.schemas.interview import (
    InterviewCreate,
    InterviewResponse,
    InterviewDetailResponse,
    InterviewQuestionResponse,
    AnswerSubmit,
    AnswerResponse,
)
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/interviews", tags=["Interviews"])


def _format_interview_response(session: InterviewSession) -> dict:
    return {
        "id": session.id,
        "user_id": session.user_id,
        "subject_id": session.subject_id,
        "subject_name": session.subject.name if session.subject else None,
        "topic_id": session.topic_id,
        "topic_name": session.topic.name if session.topic else None,
        "status": session.status,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "current_question_number": session.current_question_number,
    }


def _format_interview_question(iq: InterviewQuestion) -> dict:
    return {
        "id": iq.id,
        "question_id": iq.question_id,
        "order": iq.order,
        "question_text": iq.question.question_text if iq.question else "",
        "difficulty": iq.question.difficulty if iq.question else "EASY",
        "is_answered": iq.answer is not None,
        "answer": (
            {
                "id": iq.answer.id,
                "interview_question_id": iq.answer.interview_question_id,
                "answer_text": iq.answer.answer_text,
                "submitted_at": iq.answer.submitted_at,
            }
            if iq.answer
            else None
        ),
    }


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def start_interview(
    payload: InterviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )

    topic = None
    if payload.topic_id is not None:
        topic = (
            db.query(Topic)
            .filter(Topic.id == payload.topic_id, Topic.subject_id == payload.subject_id)
            .first()
        )
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found for the selected subject",
            )

    # Create new interview session
    session = InterviewSession(
        user_id=current_user.id,
        subject_id=payload.subject_id,
        topic_id=payload.topic_id,
        status="IN_PROGRESS",
        started_at=datetime.utcnow(),
        current_question_number=1,
    )
    db.add(session)
    db.flush()

    # Query questions for this subject/topic
    query = db.query(Question).filter(Question.subject_id == payload.subject_id)
    if payload.topic_id is not None:
        topic_questions = query.filter(Question.topic_id == payload.topic_id).all()
        if topic_questions:
            questions = topic_questions
        else:
            questions = query.all()
    else:
        questions = query.all()

    # If no questions found specifically, fetch any available questions in the DB
    if not questions:
        questions = db.query(Question).limit(5).all()

    # Assign up to 5 questions to this interview session
    selected_questions = questions[:5]
    for idx, q in enumerate(selected_questions):
        iq = InterviewQuestion(
            interview_id=session.id,
            question_id=q.id,
            order=idx + 1,
        )
        db.add(iq)

    db.commit()
    db.refresh(session)

    return _format_interview_response(session)


@router.get("", response_model=List[InterviewResponse])
def get_interviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interviews = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.started_at.desc())
        .all()
    )
    return [_format_interview_response(i) for i in interviews]


@router.get("/{interview_id}", response_model=InterviewDetailResponse)
def get_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == interview_id,
            InterviewSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )

    response_data = _format_interview_response(session)
    response_data["questions"] = [
        _format_interview_question(iq) for iq in session.interview_questions
    ]
    return response_data


@router.get("/{interview_id}/questions", response_model=List[InterviewQuestionResponse])
def get_interview_questions(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == interview_id,
            InterviewSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )

    return [_format_interview_question(iq) for iq in session.interview_questions]


@router.post(
    "/{interview_id}/questions/{question_id}/answer",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_answer(
    interview_id: int,
    question_id: int,
    payload: AnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == interview_id,
            InterviewSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )

    if session.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview is already completed",
        )

    # Match by question_id or interview_question_id for maximum convenience
    iq = (
        db.query(InterviewQuestion)
        .filter(
            InterviewQuestion.interview_id == interview_id,
            (
                (InterviewQuestion.question_id == question_id)
                | (InterviewQuestion.id == question_id)
            ),
        )
        .first()
    )
    if not iq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question does not belong to this interview session",
        )

    # Create or update existing answer
    answer = db.query(Answer).filter(Answer.interview_question_id == iq.id).first()
    if answer:
        answer.answer_text = payload.answer_text.strip()
        answer.submitted_at = datetime.utcnow()
    else:
        answer = Answer(
            interview_question_id=iq.id,
            answer_text=payload.answer_text.strip(),
            submitted_at=datetime.utcnow(),
        )
        db.add(answer)

    # Advance current_question_number if appropriate
    if iq.order >= session.current_question_number:
        session.current_question_number = iq.order + 1

    db.commit()
    db.refresh(answer)

    return answer


@router.post("/{interview_id}/complete", response_model=InterviewResponse)
def complete_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == interview_id,
            InterviewSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )

    session.status = "COMPLETED"
    session.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(session)

    return _format_interview_response(session)

