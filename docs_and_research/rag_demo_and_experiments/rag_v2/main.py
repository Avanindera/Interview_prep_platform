"""
=============================================================================
         AI-POWERED DUAL-SOURCE INTERVIEW RAG PLATFORM (v2.0)
=============================================================================
Workflow:
  1. User enters Topic/Keyword.
  2. System checks Offline Cache Database (FAISS vector store).
     - If Cosine Similarity >= Threshold (e.g. 0.68): OFFLINE HIT!
     - Uses local knowledge base instantly without network calls.
  3. If Offline Miss / Score below threshold:
     - Discovers & extracts top GitHub interview repository.
     - Discovers & extracts top GeeksforGeeks technical article.
     - Cross-compares both sources with Gemini to formulate the BEST question.
     - Caches the synthesized material into local offline database for future queries.
  4. Candidate provides an answer.
  5. Gemini evaluates the answer (Score, Verdict, Strengths, Gaps, Misconceptions).
  6. Adaptive Follow-Up Engine triggers targeted questions (e.g. testing Queue vs Stack
     if candidate had misconceptions on BFS).
=============================================================================
"""

import os
import sys
import time

# Force UTF-8 encoding on standard output for Windows console compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from dotenv import load_dotenv
load_dotenv()
load_dotenv(os.path.join(PARENT_DIR, ".env"))

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

from rag_v2.sources.offline_store import OfflineKnowledgeStore, DEFAULT_THRESHOLD
from rag_v2.sources.github_retriever import GitHubRetriever
from rag_v2.sources.gfg_retriever import GFGRetriever
from rag_v2.interviewer.gemini_client import GEMINI_MODEL
from rag_v2.interviewer.question_generator import generate_question_from_offline, compare_and_generate_best_question, normalize_topic_query
from rag_v2.interviewer.evaluator import evaluate_candidate_response
from rag_v2.interviewer.follow_up_engine import generate_adaptive_follow_up, evaluate_follow_up_answer

from typing import Dict, Any, List
import re

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def format_feedback_clean(feedback: str) -> str:
    """Cleans up markdown formatting for clean terminal output."""
    cleaned = feedback.strip()
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    return cleaned


def display_evaluation_report(eval_result: Dict[str, Any]):
    """Renders candidate evaluation in a clean, human-reviewed CLI report."""
    raw = eval_result.get("raw_evaluation", "")
    score = eval_result.get("score")
    verdict = eval_result.get("verdict", "")

    score_str = f"{score:.1f} / 10.0" if score is not None else "N/A"
    verdict_str = verdict if verdict else "Evaluated"

    print("-" * 70)
    print("ASSESSMENT REPORT")
    print(f"Status : {verdict_str:<28} Score : {score_str}")
    print("-" * 70)

    def extract_bullets(section_text: str) -> List[str]:
        items = []
        for line in section_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[-*•]\s*", "", line)
            line = re.sub(r"\[Point \d+\]", "", line).strip()
            if line:
                items.append(line)
        return items

    good_match = re.search(r"(?:What was good|Strengths)[:\s]*\n(.*?)(?=(?:What is missing|Specific Misconception|How to improve|Ideal Answer|\Z))", raw, re.DOTALL | re.IGNORECASE)
    missing_match = re.search(r"(?:What is missing or incorrect|Gaps|Weaknesses)[:\s]*\n(.*?)(?=(?:Specific Misconception|How to improve|Ideal Answer|\Z))", raw, re.DOTALL | re.IGNORECASE)
    misconception_match = re.search(r"(?:Specific Misconception|Misconception)[:\s]*\n(.*?)(?=(?:How to improve|Ideal Answer|\Z))", raw, re.DOTALL | re.IGNORECASE)
    improve_match = re.search(r"(?:How to improve|Improvement|Recommendations)[:\s]*\n(.*?)(?=(?:Ideal Answer|\Z))", raw, re.DOTALL | re.IGNORECASE)
    ideal_match = re.search(r"(?:Ideal Answer|Reference Answer)[:\s]*\n(.*?)(?=(?:Follow-up Question|\Z))", raw, re.DOTALL | re.IGNORECASE)

    has_parsed = False

    if good_match and good_match.group(1).strip():
        items = extract_bullets(good_match.group(1))
        if items:
            has_parsed = True
            print("\nStrengths:")
            for item in items:
                print(f"  + {item}")

    if missing_match and missing_match.group(1).strip():
        items = extract_bullets(missing_match.group(1))
        if items:
            has_parsed = True
            print("\nGaps / Inaccuracies:")
            for item in items:
                print(f"  - {item}")

    if misconception_match:
        misc = misconception_match.group(1).strip()
        misc_clean = re.sub(r"\[.*?\]", "", misc).strip()
        if misc_clean and misc_clean.lower() not in {"none", "none.", "none detected", "none detected.", "n/a"}:
            has_parsed = True
            print("\nKey Conceptual Misconception:")
            for l in misc_clean.split("\n"):
                if l.strip():
                    print(f"  ! {l.strip()}")

    if improve_match and improve_match.group(1).strip():
        items = extract_bullets(improve_match.group(1))
        if items:
            has_parsed = True
            print("\nRecommendations:")
            for item in items:
                print(f"  * {item}")

    if ideal_match and ideal_match.group(1).strip():
        ideal_text = ideal_match.group(1).strip()
        ideal_text = re.sub(r"^#+\s*", "", ideal_text, flags=re.MULTILINE)
        if ideal_text:
            has_parsed = True
            print("\nReference Solution:")
            for line in ideal_text.split("\n"):
                print(f"    {line}")

    if not has_parsed:
        cleaned = re.sub(r"^Score:.*?\n", "", raw, flags=re.IGNORECASE)
        cleaned = re.sub(r"^Verdict:.*?\n", "", cleaned, flags=re.IGNORECASE)
        cleaned = format_feedback_clean(cleaned)
        print(cleaned.strip())

    print("\n" + "-" * 70)


def main():
    print("-" * 70)
    print("  Interview Practice CLI (v2.1)")
    print("  Curated knowledge base with on-demand repository search.")
    print("  Type a topic or concept to begin (or 'exit' to quit).")
    print("-" * 70)

    print("Initializing index...", end=" ", flush=True)
    t0 = time.time()
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    offline_store = OfflineKnowledgeStore(model=embedding_model, threshold=DEFAULT_THRESHOLD)
    print(f"ready ({len(offline_store.topics_data)} topics loaded in {time.time()-t0:.1f}s)")

    github_retriever = GitHubRetriever()
    gfg_retriever = GFGRetriever()

    while True:
        try:
            print()
            user_query = input("topic> ").strip()
            if not user_query:
                continue
            if user_query.lower() in {"exit", "quit", "q"}:
                print("\nSession ended. Good luck with your preparation!\n")
                break
            if user_query.lower() in {"help", "?"}:
                print("  Examples: 'binary search', 'lru cache', 'bfs', 'database indexing', 'red-black tree'")
                continue

            print(f"-> Resolving '{user_query}'...", end=" ", flush=True)
            offline_match = offline_store.search_offline(user_query, top_k=5)
            best_score = offline_match["best_score"]
            threshold = offline_match["threshold"]
            effective_query = user_query

            if not offline_match["matched"]:
                normalized = normalize_topic_query(user_query)
                if normalized.lower() != user_query.lower():
                    norm_match = offline_store.search_offline(normalized, top_k=5)
                    if norm_match["matched"]:
                        offline_match = norm_match
                        best_score = norm_match["best_score"]
                        effective_query = normalized

            interview_question = ""
            ideal_ref_answer = ""
            reference_context = ""
            source_attribution = ""

            if offline_match["matched"]:
                matched_topic = offline_match["best_topic"]
                print(f"found in local cache [{matched_topic}]")
                print("-> Preparing challenge...", end=" ", flush=True)

                source_attribution = f"Local Library ({matched_topic})"
                ref_blocks = [r["chunk"]["text"] for r in offline_match["results"]]
                reference_context = "\n\n".join(ref_blocks)
                interview_question = generate_question_from_offline(effective_query, offline_match["results"])
                print("done.")

            else:
                print("cache miss.")
                effective_query = normalize_topic_query(user_query)
                print(f"-> Querying references for '{effective_query}'...")

                print("   Fetching repository...", end=" ", flush=True)
                top_repo = github_retriever.search_best_repository(effective_query)
                github_chunks = []
                if top_repo:
                    try:
                        repo_dir = github_retriever.download_and_extract_repo(top_repo)
                        github_chunks = github_retriever.extract_and_chunk_repo(repo_dir, top_repo, effective_query)
                        print(f"ok ({top_repo['full_name']}, {len(github_chunks)} chunks)")
                    except Exception as e:
                        print(f"error ({e})")
                else:
                    print("no matches")

                print("   Fetching technical docs...", end=" ", flush=True)
                gfg_chunks = gfg_retriever.retrieve_and_chunk_gfg(effective_query)
                print(f"ok ({len(gfg_chunks)} chunks)")

                all_online_chunks = github_chunks + gfg_chunks
                if not all_online_chunks:
                    print("-> Error: Unable to retrieve reference material for this topic. Try another keyword.")
                    continue

                print("-> Synthesizing curriculum benchmarks...", end=" ", flush=True)
                best_q, ideal_ans, comp_summary = compare_and_generate_best_question(user_query, github_chunks, gfg_chunks)
                interview_question = best_q
                ideal_ref_answer = ideal_ans
                source_attribution = f"External References ({len(all_online_chunks)} sources)"

                ref_texts = [c["text"] for c in all_online_chunks[:6]]
                reference_context = "\n\n".join(ref_texts)

                offline_store.save_dynamic_cache(
                    topic=user_query,
                    chunks=all_online_chunks,
                    generated_qa={"question": best_q, "ideal_answer": ideal_ans}
                )
                print("done.")

            print("\n" + "-" * 70)
            print(f"CHALLENGE: {user_query.title()}")
            print(f"Source   : {source_attribution}")
            print("-" * 70)
            print(f"\n{interview_question.strip()}\n")
            print("-" * 70)
            print("Your response (type your answer, then press Enter):")
            user_ans = input("\n> ").strip()
            if not user_ans or user_ans.lower() in {"exit", "quit"}:
                print("Skipped.\n")
                continue

            print("\nAnalyzing answer against reference criteria...", end=" ", flush=True)
            eval_result = evaluate_candidate_response(
                topic=user_query,
                question=interview_question,
                candidate_answer=user_ans,
                reference_context=reference_context,
                ideal_reference_answer=ideal_ref_answer
            )
            print("done.\n")

            display_evaluation_report(eval_result)

            # Instant follow-up: use pre-generated question from evaluation (0ms wait)
            follow_up_q = eval_result.get("follow_up_question")
            if not follow_up_q:
                print("Preparing follow-up probe...", end=" ", flush=True)
                follow_up_q = generate_adaptive_follow_up(
                    topic=user_query,
                    original_question=interview_question,
                    candidate_answer=user_ans,
                    evaluation=eval_result,
                    reference_context=reference_context
                )
                print("done.\n")

            while True:
                print("-" * 70)
                print("FOLLOW-UP PROBE")
                print("-" * 70)
                print(f"\n{follow_up_q.strip()}\n")
                print("-" * 70)

                fu_ans = input("Your response [Enter to skip] > ").strip()
                if not fu_ans or fu_ans.lower() in {"skip", "next", "exit", "n"}:
                    break

                print("\nReviewing follow-up response...", end=" ", flush=True)
                fu_feedback = evaluate_follow_up_answer(
                    topic=user_query,
                    follow_up_question=follow_up_q,
                    candidate_answer=fu_ans,
                    reference_context=reference_context
                )
                print("done.\n")

                print("-" * 70)
                print("FOLLOW-UP FEEDBACK")
                print("-" * 70)
                print(format_feedback_clean(str(fu_feedback)))
                print("-" * 70)

                # Precomputed next question for instant multi-turn follow-ups
                next_q = getattr(fu_feedback, "next_follow_up", "")

                another = input("\nContinue with another follow-up on this topic? [y/N] > ").strip().lower()
                if another not in {"y", "yes"}:
                    break

                if next_q:
                    follow_up_q = next_q
                else:
                    print("Preparing next probe...", end=" ", flush=True)
                    follow_up_q = generate_adaptive_follow_up(
                        topic=user_query,
                        original_question=follow_up_q,
                        candidate_answer=fu_ans,
                        evaluation={"verdict": "Partially Correct", "score": 7.0, "misconception": "None"},
                        reference_context=reference_context
                    )
                    print("done.\n")

        except KeyboardInterrupt:
            print("\n\nSession terminated.")
            break
        except Exception as e:
            print(f"\n[error] An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
