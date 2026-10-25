from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.models.interview import InterviewSession, InterviewQuestion, Answer
from app.schemas.dashboard import DashboardResponse, RecentInterviewItem
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_interviews = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .count()
    )

    completed_interviews = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.user_id == current_user.id,
            InterviewSession.status == "COMPLETED",
        )
        .count()
    )

    in_progress_interviews = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.user_id == current_user.id,
            InterviewSession.status == "IN_PROGRESS",
        )
        .count()
    )

    questions_answered = (
        db.query(Answer)
        .join(InterviewQuestion, Answer.interview_question_id == InterviewQuestion.id)
        .join(InterviewSession, InterviewQuestion.interview_id == InterviewSession.id)
        .filter(InterviewSession.user_id == current_user.id)
        .count()
    )

    recent_sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.started_at.desc())
        .limit(5)
        .all()
    )

    recent_interviews = [
        RecentInterviewItem(
            id=s.id,
            subject=s.subject.name if s.subject else "General",
            topic=s.topic.name if s.topic else None,
            status=s.status,
            started_at=s.started_at,
            completed_at=s.completed_at,
        )
        for s in recent_sessions
    ]

    return DashboardResponse(
        total_interviews=total_interviews,
        completed_interviews=completed_interviews,
        in_progress_interviews=in_progress_interviews,
        questions_answered=questions_answered,
        recent_interviews=recent_interviews,
    )

