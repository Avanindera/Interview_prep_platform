"""
=============================================================================
                    RAG TECHNICAL INTERVIEW SERVICE
=============================================================================
Wraps the Dual-Source RAG pipeline (Offline FAISS Knowledge Base + Online
GitHub & GeeksforGeeks Discoverer + Gemini synthesis) to provide:
1. Dynamic, grounded technical interview question generation.
2. Technical answer evaluation (Score /10, Verdict, Strengths, Gaps, Misconceptions).
3. Adaptive misconception-driven follow-up engine.
=============================================================================
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.rag.sources.offline_store import OfflineKnowledgeStore, DEFAULT_THRESHOLD
from app.rag.sources.github_retriever import GitHubRetriever
from app.rag.sources.gfg_retriever import GFGRetriever
from app.rag.interviewer.question_generator import (
    generate_question_from_offline,
    compare_and_generate_best_question,
    normalize_topic_query,
)
from app.rag.interviewer.evaluator import evaluate_candidate_response
from app.rag.interviewer.follow_up_engine import (
    generate_adaptive_follow_up,
    evaluate_follow_up_answer,
)

# Shared singleton instances
_offline_store: Optional[OfflineKnowledgeStore] = None
_embedding_model = None
_github_retriever: Optional[GitHubRetriever] = None
_gfg_retriever: Optional[GFGRetriever] = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[WARN] Failed to load embedding model: {e}")
    return _embedding_model


def get_offline_store() -> OfflineKnowledgeStore:
    global _offline_store
    if _offline_store is None:
        db_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "rag",
            "offline_db",
        )
        emb = get_embedding_model()
        _offline_store = OfflineKnowledgeStore(db_dir=db_dir, model=emb, threshold=0.55)
    return _offline_store


def get_github_retriever() -> GitHubRetriever:
    global _github_retriever
    if _github_retriever is None:
        cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "rag",
            "repo_cache",
        )
        token = os.getenv("GITHUB_TOKEN", "").strip()
        _github_retriever = GitHubRetriever(token=token, cache_dir=cache_dir)
    return _github_retriever


def get_gfg_retriever() -> GFGRetriever:
    global _gfg_retriever
    if _gfg_retriever is None:
        cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "rag",
            "gfg_cache",
        )
        _gfg_retriever = GFGRetriever(cache_dir=cache_dir)
    return _gfg_retriever


def generate_rag_question(topic: str) -> Dict[str, Any]:
    """
    Generates a high-quality interview question for a given topic using:
    1. Tier-1 Offline FAISS Vector Knowledge Base.
    2. Tier-2 Dual-Source Online Discovery (GitHub + GeeksforGeeks) with automatic caching.
    """
    store = get_offline_store()
    normalized_topic = normalize_topic_query(topic)
    
    # 1. Check offline knowledge store
    search_res = store.search_offline(normalized_topic, top_k=5)
    
    if search_res.get("matched") and search_res.get("results"):
        q_text = generate_question_from_offline(normalized_topic, search_res["results"])
        return {
            "source": "OFFLINE_CACHE",
            "topic": normalized_topic,
            "best_matched_topic": search_res.get("best_topic"),
            "similarity_score": search_res.get("best_score"),
            "question": q_text,
            "reference_context": "\n\n".join([r["chunk"]["text"] for r in search_res["results"][:3]]),
            "ideal_answer": search_res["results"][0]["chunk"].get("ideal_answer", ""),
        }
    
    # 2. Dual-Source Online Discovery Fallback
    gh = get_github_retriever()
    gfg = get_gfg_retriever()
    
    gh_chunks = gh.search_and_extract_chunks(normalized_topic)
    gfg_chunks = gfg.search_and_extract_chunks(normalized_topic)
    
    best_q, ideal_ans, comp_summary = compare_and_generate_best_question(
        normalized_topic, gh_chunks, gfg_chunks
    )
    
    # Cache online discovery into local dynamic cache for instant future retrieval
    all_chunks = gh_chunks + gfg_chunks
    if all_chunks:
        store.save_dynamic_cache(
            topic=normalized_topic,
            chunks=all_chunks,
            generated_qa={"question": best_q, "ideal_answer": ideal_ans},
        )
        
    ref_context = "\n\n".join([c.get("text", "") for c in all_chunks[:4]])
    
    return {
        "source": "ONLINE_DUAL_SOURCE_SYNTHESIS",
        "topic": normalized_topic,
        "question": best_q,
        "ideal_answer": ideal_ans,
        "comparison_summary": comp_summary,
        "reference_context": ref_context,
    }


def generate_rag_questions_batch(topic: str, count: int = 3) -> List[str]:
    """
    Generates 'count' progressive, grounded interview questions in a single fast LLM turn,
    grounded in retrieved RAG context (offline FAISS or online discovery).
    """
    store = get_offline_store()
    normalized_topic = normalize_topic_query(topic) if len(topic.split()) <= 4 else topic

    # 1. Search offline knowledge store
    search_res = store.search_offline(normalized_topic, top_k=5)
    context_str = ""
    offline_preset_questions: List[str] = []

    if search_res.get("matched") and search_res.get("results"):
        context_str = "\n\n".join([r["chunk"]["text"] for r in search_res["results"][:4]])
        for r in search_res["results"]:
            q_cand = r["chunk"].get("question")
            if q_cand and q_cand not in offline_preset_questions:
                offline_preset_questions.append(q_cand)
    else:
        # Dual-source discovery
        try:
            gh = get_github_retriever()
            gfg = get_gfg_retriever()
            gh_chunks = gh.search_and_extract_chunks(normalized_topic)
            gfg_chunks = gfg.search_and_extract_chunks(normalized_topic)
            all_chunks = gh_chunks + gfg_chunks
            context_str = "\n\n".join([c.get("text", "") for c in all_chunks[:4]])
        except Exception as e:
            print(f"[WARN] Online discovery error in batch gen: {e}")
            context_str = f"Topic: {normalized_topic}"

    # 2. Call Gemini ONCE to generate the batch of progressive questions
    from app.rag.interviewer.gemini_client import call_gemini
    prompt = f"""You are a Principal Software Engineer and Senior Technical Interviewer.
TOPIC: {normalized_topic}

RETRIEVED TECHNICAL GROUND TRUTH:
{context_str[:2500] if context_str else f"Topic: {normalized_topic}"}

TASK:
Formulate exactly {count} progressive, high-quality technical interview questions suitable for a college student / software engineering candidate.
The questions should progress naturally:
- Foundational invariants and core data structures
- Time and space complexity with constraints
- Edge cases, termination conditions, or error scenarios
- Practical optimizations or scale variations (e.g. 0-1 variations, caching, concurrent access)

FORMAT INSTRUCTIONS:
- Return each question on a new line prefixed with 'Q: '
- Do NOT include answers or solutions
- Return ONLY the questions, no conversational fluff.
"""
    try:
        raw_res = call_gemini(prompt)
        questions = []
        for line in raw_res.strip().splitlines():
            line_clean = line.strip()
            if line_clean.startswith("Q:") or line_clean.startswith("Q1:") or line_clean.startswith("Q2:") or line_clean.startswith("Q3:") or line_clean.startswith("Q4:") or line_clean.startswith("Q5:"):
                q_text = line_clean.split(":", 1)[1].strip()
                if q_text:
                    questions.append(q_text)
            elif re.match(r"^\d+[\.\)]\s*", line_clean):
                q_text = re.sub(r"^\d+[\.\)]\s*", "", line_clean).strip()
                if q_text:
                    questions.append(q_text)

        if len(questions) >= count:
            return questions[:count]
        elif questions:
            # Pad with preset offline questions or templates if needed
            while len(questions) < count:
                if offline_preset_questions:
                    cand = offline_preset_questions.pop(0)
                    if cand not in questions:
                        questions.append(cand)
                        continue
                questions.append(f"Explain the practical trade-offs, space/time complexity, and edge cases of {normalized_topic}.")
            return questions[:count]
    except Exception as e:
        print(f"[WARN] Batch question generation error: {e}")

    # Fallback if Gemini failed
    fallback_list = []
    if offline_preset_questions:
        fallback_list.extend(offline_preset_questions[:count])
    while len(fallback_list) < count:
        idx = len(fallback_list) + 1
        fallback_list.append(f"Explain the core mechanisms, implementation invariants, and complexity of {normalized_topic} (Part {idx}).")
    return fallback_list[:count]


def evaluate_technical_answer(
    topic: str,
    question: str,
    candidate_answer: str,
    reference_context: Optional[str] = None,
    ideal_answer: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates candidate's answer technically using Gemini and retrieved knowledge.
    Returns score, verdict, strengths, gaps, misconceptions, and follow-up question.
    """
    if not reference_context:
        # Retrieve context from offline store if not provided
        store = get_offline_store()
        search_res = store.search_offline(topic, top_k=3)
        if search_res.get("results"):
            reference_context = "\n\n".join([r["chunk"]["text"] for r in search_res["results"]])
        else:
            reference_context = f"Topic: {topic}. Question: {question}."

    return evaluate_candidate_response(
        topic=topic,
        question=question,
        candidate_answer=candidate_answer,
        reference_context=reference_context,
        ideal_reference_answer=ideal_answer,
    )


def evaluate_follow_up(
    topic: str,
    follow_up_question: str,
    candidate_answer: str,
    reference_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluates candidate's response to an adaptive follow-up question."""
    if not reference_context:
        reference_context = f"Topic: {topic}."
    fb = evaluate_follow_up_answer(
        topic=topic,
        follow_up_question=follow_up_question,
        candidate_answer=candidate_answer,
        reference_context=reference_context,
    )
    return {
        "feedback": fb.feedback,
        "next_follow_up": fb.next_follow_up,
    }
