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

    answers = (
        db.query(Answer)
        .join(InterviewQuestion, Answer.interview_question_id == InterviewQuestion.id)
        .join(InterviewSession, InterviewQuestion.interview_id == InterviewSession.id)
        .filter(InterviewSession.user_id == current_user.id)
        .all()
    )
    questions_answered = len(answers)

    # Calculate average score & speech delivery pass rate
    scores = [a.technical_score for a in answers if a.technical_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    good_speech_count = sum(1 for a in answers if a.speech_verdict == "GOOD")
    speech_pass_rate = round((good_speech_count / questions_answered * 100), 1) if questions_answered > 0 else None

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
            subject=s.subject.name if s.subject else (s.custom_topic or "AI Dynamic Interview"),
            topic=s.topic.name if s.topic else (s.custom_topic or "General"),
            status=s.status,
            score=s.overall_score,
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
        average_score=avg_score,
        speech_pass_rate=speech_pass_rate,
        recent_interviews=recent_interviews,
    )
