"""
=============================================================================
                    UNIFIED INTERVIEW EVALUATION SERVICE
=============================================================================
Combines:
1. Technical Evaluation (from RAG + Gemini): Score /10, Verdict, Strengths, Gaps, Misconceptions, Ideal Answer.
2. Speech & Delivery Evaluation (from Whisper + ML Classifier + Features): Fillers, Density, Hedging, Confidence, Delivery Verdict.
3. Adaptive Follow-Up Question Generator.
=============================================================================
"""

import os
from typing import Dict, Any, Optional

from app.services.rag_service import evaluate_technical_answer, evaluate_follow_up
from app.services.speech_service import evaluate_speech_delivery, transcribe_audio_file


def evaluate_submission(
    topic: str,
    question: str,
    answer_text: Optional[str] = None,
    audio_path: Optional[str] = None,
    reference_context: Optional[str] = None,
    ideal_answer: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates candidate's submission across Technical (and Speech dimensions if audio provided).
    For typed answers (no audio_path), speech metrics are omitted (set to None).
    """
    final_text = (answer_text or "").strip()
    transcription_performed = False

    # 1. Transcribe audio if provided
    is_audio = bool(audio_path and os.path.exists(audio_path))
    if is_audio:
        try:
            transcribed = transcribe_audio_file(audio_path)
            if transcribed:
                final_text = transcribed
                transcription_performed = True
        except Exception as e:
            print(f"[WARN] Audio transcription error: {e}")

    if not final_text:
        final_text = "No response provided."

    # 2. Run AI Speech & Delivery Evaluation ONLY if spoken audio is provided
    if is_audio:
        speech_res = evaluate_speech_delivery(final_text)
    else:
        speech_res = {}

    # 3. Run RAG Technical Evaluation
    try:
        tech_res = evaluate_technical_answer(
            topic=topic,
            question=question,
            candidate_answer=final_text,
            reference_context=reference_context,
            ideal_answer=ideal_answer,
        )
    except Exception as e:
        print(f"[WARN] RAG technical evaluation error: {e}")
        tech_res = {
            "score": 6.0,
            "verdict": "Partially Correct",
            "raw_evaluation": f"Technical evaluation notice: {e}\n\nCandidate response recorded.",
            "misconception": "None detected",
            "follow_up_question": "Can you elaborate on your solution and analyze the edge cases?",
        }

    return {
        "answer_text": final_text,
        "transcription_performed": transcription_performed,
        "audio_path": audio_path if is_audio else None,
        # Technical Evaluation
        "technical_score": tech_res.get("score", 5.0),
        "technical_verdict": tech_res.get("verdict", "Partially Correct"),
        "technical_feedback": tech_res.get("raw_evaluation", ""),
        "misconception": tech_res.get("misconception", "None"),
        "follow_up_question": tech_res.get("follow_up_question", ""),
        # Speech Evaluation (None for typed answers)
        "speech_verdict": speech_res.get("verdict") if is_audio else None,
        "speech_confidence": speech_res.get("confidence") if is_audio else None,
        "filler_count": speech_res.get("filler_count") if is_audio else None,
        "filler_density": speech_res.get("filler_density") if is_audio else None,
        "hedging_count": speech_res.get("hedging_count") if is_audio else None,
        "technical_keyword_count": speech_res.get("technical_keyword_count") if is_audio else None,
        "technical_density": speech_res.get("technical_density") if is_audio else None,
        "lexical_diversity": speech_res.get("lexical_diversity") if is_audio else None,
        "speech_feedback": speech_res.get("feedback") if is_audio else None,
        "semantic_depth": speech_res.get("semantic_depth") if is_audio else None,
        "keybert_keyphrases": (", ".join(f"{p} ({s:.2f})" for p, s in speech_res.get("keybert_keyphrases", [])[:6]) if (is_audio and speech_res.get("keybert_keyphrases")) else None),
    }
