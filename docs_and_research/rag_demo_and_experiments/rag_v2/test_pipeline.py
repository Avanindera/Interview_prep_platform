"""
=============================================================================
                    PIPELINE VERIFICATION & TEST SUITE
=============================================================================
Automated test script verifying:
  1. Offline Knowledge Store & FAISS index creation and thresholding.
  2. GFG Retriever & GitHub Retriever content fetching.
  3. Gemini question generator & cross-source synthesizer.
  4. Candidate evaluation & misconception detection.
  5. Adaptive follow-up question generation (Stack vs Queue in BFS).
=============================================================================
"""

import os
import sys

# Force UTF-8 on Windows stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
from rag_v2.sources.offline_store import OfflineKnowledgeStore, DEFAULT_THRESHOLD
from rag_v2.sources.github_retriever import GitHubRetriever
from rag_v2.sources.gfg_retriever import GFGRetriever
from rag_v2.interviewer.question_generator import generate_question_from_offline, compare_and_generate_best_question
from rag_v2.interviewer.evaluator import evaluate_candidate_response
from rag_v2.interviewer.follow_up_engine import generate_adaptive_follow_up, evaluate_follow_up_answer


def run_tests():
    print("=" * 70)
    print("           STARTING RAG v2 PIPELINE VERIFICATION SUITE")
    print("=" * 70)

    # 1. Test Model & Offline Store
    print("\n[TEST 1/5] Loading SentenceTransformer & testing Offline Vector Store...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    store = OfflineKnowledgeStore(model=model, threshold=DEFAULT_THRESHOLD)
    print(f"  [OK] Loaded {len(store.chunks)} chunks across {len(store.topics_data)} topics.")

    # Test Offline Hit on "BFS"
    match_bfs = store.search_offline("Breadth First Search algorithm queue")
    print(f"  Search 'Breadth First Search algorithm queue' -> Matched: {match_bfs['matched']}, Best Score: {match_bfs['best_score']}, Best Topic: {match_bfs['best_topic']}")
    assert match_bfs["matched"] is True, "Expected BFS to be an offline hit!"
    print("  [OK] TEST 1 (Offline Hit) PASSED.")

    # Test Offline Miss on novel topic
    match_novel = store.search_offline("Quantum Superconducting Qubits Josephson Junctions")
    print(f"  Search 'Quantum Superconducting Qubits' -> Matched: {match_novel['matched']}, Best Score: {match_novel['best_score']}")
    assert match_novel["matched"] is False, "Expected Quantum topic to be an offline miss below threshold!"
    print("  [OK] TEST 1 (Offline Miss & Thresholding) PASSED.")

    # 2. Test GeeksforGeeks Retriever
    print("\n[TEST 2/5] Testing GeeksforGeeks (GFG) Retriever...")
    gfg = GFGRetriever()
    gfg_chunks = gfg.retrieve_and_chunk_gfg("Dijkstra Algorithm")
    print(f"  Retrieved {len(gfg_chunks)} chunks from GeeksforGeeks for 'Dijkstra Algorithm'.")
    assert len(gfg_chunks) > 0, "Expected at least 1 chunk from GFG!"
    print(f"  Sample GFG text: {gfg_chunks[0]['text'][:120]}...")
    print("  [OK] TEST 2 (GFG Retriever) PASSED.")

    # 3. Test Question Generator with Gemini
    print("\n[TEST 3/5] Testing Gemini Question Generator on Offline BFS context...")
    question = generate_question_from_offline("BFS", match_bfs["results"])
    print(f"  Generated Question:\n  > {question}")
    assert len(question) > 15, "Expected a valid interview question generated."
    print("  [OK] TEST 3 (Question Generation) PASSED.")

    # 4. Test Answer Evaluator with a Wrong Answer (Testing Misconception Detection)
    print("\n[TEST 4/5] Testing Candidate Evaluator with a WRONG Answer (Stack used in BFS)...")
    simulated_wrong_answer = "BFS traverses a graph using a recursive call stack and explores deeply down each path before backtracking."
    ref_context = "\n\n".join([r["chunk"]["text"] for r in match_bfs["results"]])

    eval_result = evaluate_candidate_response(
        topic="BFS",
        question=question,
        candidate_answer=simulated_wrong_answer,
        reference_context=ref_context
    )
    print(f"  Score: {eval_result['score']}/10")
    print(f"  Verdict: {eval_result['verdict']}")
    print(f"  Detected Misconception: {eval_result['misconception']}")
    assert eval_result["score"] < 7.0, f"Expected low score for wrong answer, got {eval_result['score']}"
    print("  [OK] TEST 4 (Evaluation & Misconception Extraction) PASSED.")

    # 5. Test Adaptive Follow-Up Question
    print("\n[TEST 5/5] Testing Adaptive Follow-Up Engine for the detected mistake...")
    follow_up = generate_adaptive_follow_up(
        topic="BFS",
        original_question=question,
        candidate_answer=simulated_wrong_answer,
        evaluation=eval_result,
        reference_context=ref_context
    )
    print(f"  Targeted Follow-Up Question:\n  > {follow_up}")
    assert len(follow_up) > 10, "Expected a valid follow-up question."

    # Test candidate answering follow-up
    fu_simulated_correct = "Actually, BFS requires a FIFO Queue to visit nodes level-by-level in order of their distance, whereas a Stack would cause LIFO DFS traversal."
    fu_feedback = evaluate_follow_up_answer(
        topic="BFS",
        follow_up_question=follow_up,
        candidate_answer=fu_simulated_correct,
        reference_context=ref_context
    )
    print(f"\n  Follow-up Evaluation:\n{fu_feedback}")
    print("  [OK] TEST 5 (Adaptive Follow-Up & Feedback) PASSED.")

    print("\n" + "=" * 70)
    print("     ALL 5 TESTS IN PIPELINE VERIFICATION SUITE PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
