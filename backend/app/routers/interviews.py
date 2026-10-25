import os
import shutil
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
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
    FollowUpSubmit,
)
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.services.rag_service import generate_rag_question, evaluate_follow_up, generate_rag_questions_batch
from app.services.evaluation_service import evaluate_submission
from app.services.speech_service import transcribe_audio_file

router = APIRouter(prefix="/interviews", tags=["Interviews"])

UPLOAD_AUDIO_DIR = os.path.join(settings.UPLOAD_DIR, "audio")
os.makedirs(UPLOAD_AUDIO_DIR, exist_ok=True)


def _format_interview_response(session: InterviewSession) -> dict:
    return {
        "id": session.id,
        "user_id": session.user_id,
        "subject_id": session.subject_id,
        "subject_name": session.subject.name if session.subject else "AI RAG Dynamic Topic",
        "topic_id": session.topic_id,
        "topic_name": session.topic.name if session.topic else (session.custom_topic or "General"),
        "generation_mode": getattr(session, "generation_mode", "CURATED"),
        "custom_topic": getattr(session, "custom_topic", None),
        "overall_score": getattr(session, "overall_score", None),
        "status": session.status,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "current_question_number": session.current_question_number,
    }


def _format_interview_question(iq: InterviewQuestion) -> dict:
    ans_data = None
    if iq.answer:
        ans = iq.answer
        ans_data = {
            "id": ans.id,
            "interview_question_id": ans.interview_question_id,
            "answer_text": ans.answer_text,
            "audio_path": ans.audio_path,
            "submitted_at": ans.submitted_at,
            "technical_score": ans.technical_score,
            "technical_verdict": ans.technical_verdict,
            "technical_feedback": ans.technical_feedback,
            "misconception": ans.misconception,
            "follow_up_question": ans.follow_up_question,
            "follow_up_answer": ans.follow_up_answer,
            "follow_up_feedback": ans.follow_up_feedback,
            "speech_verdict": ans.speech_verdict,
            "speech_confidence": ans.speech_confidence,
            "filler_count": ans.filler_count,
            "filler_density": ans.filler_density,
            "hedging_count": ans.hedging_count,
            "technical_keyword_count": ans.technical_keyword_count,
            "technical_density": ans.technical_density,
            "lexical_diversity": ans.lexical_diversity,
            "speech_feedback": ans.speech_feedback,
        }

    return {
        "id": iq.id,
        "question_id": iq.question_id,
        "order": iq.order,
        "question_text": iq.question.question_text if iq.question else "",
        "difficulty": iq.question.difficulty if iq.question else "MEDIUM",
        "is_answered": iq.answer is not None,
        "answer": ans_data,
    }


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def start_interview(
    payload: InterviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    generation_mode = payload.generation_mode or "CURATED"

    # --- MODE 1: DYNAMIC RAG INTERVIEW ---
    if generation_mode == "RAG_DYNAMIC":
        target_topic = (payload.custom_topic or "").strip()
        if not target_topic:
            if payload.topic_id:
                top = db.query(Topic).filter(Topic.id == payload.topic_id).first()
                if top:
                    target_topic = top.name
            elif payload.subject_id:
                sub = db.query(Subject).filter(Subject.id == payload.subject_id).first()
                if sub:
                    target_topic = sub.name

        if not target_topic:
            target_topic = "Data Structures and Algorithms"

        # Create session
        session = InterviewSession(
            user_id=current_user.id,
            subject_id=payload.subject_id,
            topic_id=payload.topic_id,
            generation_mode="RAG_DYNAMIC",
            custom_topic=target_topic,
            status="IN_PROGRESS",
            started_at=datetime.utcnow(),
            current_question_number=1,
        )
        db.add(session)
        db.flush()

        # Dynamically generate 1 to 5 targeted RAG questions in one fast batch
        num_q = max(1, min(payload.question_count or 3, 5))
        generated_questions = []

        try:
            q_texts = generate_rag_questions_batch(target_topic, count=num_q)
        except Exception as e:
            print(f"[WARN] Dynamic RAG batch generation fallback: {e}")
            q_texts = [
                f"Explain the core mechanisms, performance characteristics, and time/space complexity of {target_topic} (Part {i+1})."
                for i in range(num_q)
            ]

        for q_text in q_texts:
            q = Question(
                subject_id=payload.subject_id,
                topic_id=payload.topic_id,
                question_text=q_text,
                difficulty="MEDIUM",
            )
            db.add(q)
            db.flush()
            generated_questions.append(q)

        for idx, q in enumerate(generated_questions):
            iq = InterviewQuestion(
                interview_id=session.id,
                question_id=q.id,
                order=idx + 1,
            )
            db.add(iq)

        db.commit()
        db.refresh(session)
        return _format_interview_response(session)

    # --- MODE 2: CURATED STATIC / SEEDED QUESTIONS ---
    subject = None
    if payload.subject_id is not None:
        subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()

    topic = None
    if payload.topic_id is not None and payload.subject_id is not None:
        topic = (
            db.query(Topic)
            .filter(Topic.id == payload.topic_id, Topic.subject_id == payload.subject_id)
            .first()
        )

    session = InterviewSession(
        user_id=current_user.id,
        subject_id=payload.subject_id or 1,
        topic_id=payload.topic_id,
        generation_mode="CURATED",
        custom_topic=topic.name if topic else (subject.name if subject else "General"),
        status="IN_PROGRESS",
        started_at=datetime.utcnow(),
        current_question_number=1,
    )
    db.add(session)
    db.flush()

    query = db.query(Question)
    if payload.subject_id is not None:
        query = query.filter(Question.subject_id == payload.subject_id)
    if payload.topic_id is not None:
        topic_questions = query.filter(Question.topic_id == payload.topic_id).all()
        questions = topic_questions if topic_questions else query.all()
    else:
        questions = query.all()

    if not questions:
        questions = db.query(Question).limit(5).all()

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

    topic_name = session.custom_topic or (session.topic.name if session.topic else (session.subject.name if session.subject else "General"))
    question_text = iq.question.question_text if iq.question else ""

    # Run Integrated Evaluation (Technical RAG + Speech ML/Diagnostics)
    eval_res = evaluate_submission(
        topic=topic_name,
        question=question_text,
        answer_text=payload.answer_text,
    )

    answer = db.query(Answer).filter(Answer.interview_question_id == iq.id).first()
    if answer:
        answer.answer_text = eval_res["answer_text"]
        answer.submitted_at = datetime.utcnow()
    else:
        answer = Answer(
            interview_question_id=iq.id,
            answer_text=eval_res["answer_text"],
            submitted_at=datetime.utcnow(),
        )
        db.add(answer)

    # Populate Technical Evaluation
    answer.technical_score = eval_res["technical_score"]
    answer.technical_verdict = eval_res["technical_verdict"]
    answer.technical_feedback = eval_res["technical_feedback"]
    answer.misconception = eval_res["misconception"]
    answer.follow_up_question = eval_res["follow_up_question"]

    # Populate Speech Delivery Evaluation
    answer.speech_verdict = eval_res["speech_verdict"]
    answer.speech_confidence = eval_res["speech_confidence"]
    answer.filler_count = eval_res["filler_count"]
    answer.filler_density = eval_res["filler_density"]
    answer.hedging_count = eval_res["hedging_count"]
    answer.technical_keyword_count = eval_res["technical_keyword_count"]
    answer.technical_density = eval_res["technical_density"]
    answer.lexical_diversity = eval_res["lexical_diversity"]
    answer.speech_feedback = eval_res["speech_feedback"]

    # Update overall score on session
    all_answers = (
        db.query(Answer)
        .join(InterviewQuestion)
        .filter(InterviewQuestion.interview_id == session.id)
        .all()
    )
    valid_scores = [a.technical_score for a in all_answers if a.technical_score is not None]
    if valid_scores:
        session.overall_score = round(sum(valid_scores) / len(valid_scores), 2)

    if iq.order >= session.current_question_number:
        session.current_question_number = iq.order + 1

    db.commit()
    db.refresh(answer)
    return answer


@router.post(
    "/{interview_id}/questions/{question_id}/audio-answer",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_audio_answer(
    interview_id: int,
    question_id: int,
    file: UploadFile = File(...),
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

    # Save audio file
    ext = os.path.splitext(file.filename or "")[1] or ".wav"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    saved_filename = f"user_{current_user.id}_session_{interview_id}_q_{iq.id}_{timestamp}{ext}"
    saved_filepath = os.path.join(UPLOAD_AUDIO_DIR, saved_filename)

    with open(saved_filepath, "wb") as f_out:
        shutil.copyfileobj(file.file, f_out)

    topic_name = session.custom_topic or (session.topic.name if session.topic else (session.subject.name if session.subject else "General"))
    question_text = iq.question.question_text if iq.question else ""

    # Run Integrated Evaluation (Whisper Transcribe + Technical RAG + Speech ML)
    eval_res = evaluate_submission(
        topic=topic_name,
        question=question_text,
        audio_path=saved_filepath,
    )

    answer = db.query(Answer).filter(Answer.interview_question_id == iq.id).first()
    if answer:
        answer.answer_text = eval_res["answer_text"]
        answer.audio_path = saved_filepath
        answer.submitted_at = datetime.utcnow()
    else:
        answer = Answer(
            interview_question_id=iq.id,
            answer_text=eval_res["answer_text"],
            audio_path=saved_filepath,
            submitted_at=datetime.utcnow(),
        )
        db.add(answer)

    # Populate Technical Evaluation
    answer.technical_score = eval_res["technical_score"]
    answer.technical_verdict = eval_res["technical_verdict"]
    answer.technical_feedback = eval_res["technical_feedback"]
    answer.misconception = eval_res["misconception"]
    answer.follow_up_question = eval_res["follow_up_question"]

    # Populate Speech Delivery Evaluation
    answer.speech_verdict = eval_res["speech_verdict"]
    answer.speech_confidence = eval_res["speech_confidence"]
    answer.filler_count = eval_res["filler_count"]
    answer.filler_density = eval_res["filler_density"]
    answer.hedging_count = eval_res["hedging_count"]
    answer.technical_keyword_count = eval_res["technical_keyword_count"]
    answer.technical_density = eval_res["technical_density"]
    answer.lexical_diversity = eval_res["lexical_diversity"]
    answer.speech_feedback = eval_res["speech_feedback"]

    # Update overall score
    all_answers = (
        db.query(Answer)
        .join(InterviewQuestion)
        .filter(InterviewQuestion.interview_id == session.id)
        .all()
    )
    valid_scores = [a.technical_score for a in all_answers if a.technical_score is not None]
    if valid_scores:
        session.overall_score = round(sum(valid_scores) / len(valid_scores), 2)

    if iq.order >= session.current_question_number:
        session.current_question_number = iq.order + 1

    db.commit()
    db.refresh(answer)
    return answer


@router.post(
    "/{interview_id}/questions/{question_id}/follow-up",
    response_model=AnswerResponse,
    status_code=status.HTTP_200_OK,
)
def submit_follow_up(
    interview_id: int,
    question_id: int,
    payload: FollowUpSubmit,
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
    if not iq or not iq.answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer record not found for this question",
        )

    answer = iq.answer
    if not answer.follow_up_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No follow-up question was generated for this answer",
        )

    topic_name = session.custom_topic or (session.topic.name if session.topic else "General")
    fb_res = evaluate_follow_up(
        topic=topic_name,
        follow_up_question=answer.follow_up_question,
        candidate_answer=payload.follow_up_answer,
    )

    answer.follow_up_answer = payload.follow_up_answer.strip()
    answer.follow_up_feedback = fb_res.get("feedback", "Follow-up response evaluated.")

    db.commit()
    db.refresh(answer)
    return answer


@router.post(
    "/{interview_id}/questions/{question_id}/follow-up-audio",
    response_model=AnswerResponse,
    status_code=status.HTTP_200_OK,
)
def submit_follow_up_audio(
    interview_id: int,
    question_id: int,
    file: UploadFile = File(...),
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
    if not iq or not iq.answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer record not found for this question",
        )

    answer = iq.answer
    if not answer.follow_up_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No follow-up question was generated for this answer",
        )

    # Save audio file
    ext = os.path.splitext(file.filename or "")[1] or ".wav"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    saved_filename = f"user_{current_user.id}_session_{interview_id}_fu_q_{iq.id}_{timestamp}{ext}"
    saved_filepath = os.path.join(UPLOAD_AUDIO_DIR, saved_filename)

    with open(saved_filepath, "wb") as f_out:
        shutil.copyfileobj(file.file, f_out)

    try:
        transcribed_text = transcribe_audio_file(saved_filepath)
    except Exception as e:
        print(f"[WARN] Failed to transcribe follow-up audio: {e}")
        transcribed_text = "Spoken follow-up response recorded."

    if not transcribed_text:
        transcribed_text = "No clear spoken response detected."

    topic_name = session.custom_topic or (session.topic.name if session.topic else "General")
    fb_res = evaluate_follow_up(
        topic=topic_name,
        follow_up_question=answer.follow_up_question,
        candidate_answer=transcribed_text,
    )

    answer.follow_up_answer = transcribed_text.strip()
    answer.follow_up_feedback = fb_res.get("feedback", "Follow-up response evaluated.")

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
