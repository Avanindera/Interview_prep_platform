"""
=============================================================================
                    CANDIDATE ANSWER EVALUATOR
=============================================================================
Evaluates the candidate's answer strictly against reference context and
extracts specific technical misconceptions for the follow-up engine.
=============================================================================
"""

import re
from typing import Dict, Any, List, Optional
from app.rag.interviewer.gemini_client import call_gemini


def evaluate_candidate_response(
    topic: str,
    question: str,
    candidate_answer: str,
    reference_context: str,
    ideal_reference_answer: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates candidate response and produces structured assessment including
    detected misconceptions and an immediate follow-up probe.
    """
    prompt = f"""You are a Principal AI Technical Interviewer evaluating a candidate's answer.

INTERVIEW TOPIC:
{topic}

QUESTION ASKED:
{question}

CANDIDATE'S ANSWER:
{candidate_answer}

IDEAL REFERENCE ANSWER (IF AVAILABLE):
{ideal_reference_answer or "N/A"}

RETRIEVED TECHNICAL GROUND TRUTH:
{reference_context}

SCORING PARAMETERS & WEIGHTS (Total: 10 Points):
1. Conceptual Correctness & Invariants (Weight: 40% / 4.0 pts):
   - Correct core data structures and algorithmic invariants (e.g. Queue vs Stack for BFS, visited set).
2. Completeness & Edge Cases (Weight: 25% / 2.5 pts):
   - Handling boundaries, base cases, termination conditions, null/cycle checks.
3. Complexity Analysis (Weight: 20% / 2.0 pts):
   - Accurately stating and explaining Big-O asymptotic Time and Space complexities.
4. Technical Precision & Communication (Weight: 15% / 1.5 pts):
   - Clear technical terminology, sound reasoning, avoiding contradictory explanations.

YOUR EVALUATION OBJECTIVES:
1. Grade the candidate out of 10 according to the weighted rubric above.
2. Determine Verdict: Correct / Partially Correct / Incorrect.
3. Identify precisely what was good.
4. Identify what is missing or factually/conceptually incorrect.
5. Identify specific TECHNICAL MISCONCEPTIONS (e.g., saying BFS uses a Stack or recursion, forgetting visited set, confusing time complexities, forgetting O(1) constraints).
6. Provide an actionable improvement tip.
7. Provide the Ideal Answer grounded in the context.
8. Formulate a targeted, adaptive FOLLOW-UP QUESTION:
   - If Verdict is Incorrect or Partially Correct (score < 7.5): Directly probe their specific misconception or missing invariant to guide them to the right principle.
   - If Verdict is Correct (score >= 7.5): Pose an advanced deep-dive question (e.g., scale optimizations, edge cases, alternative approaches).

FORMAT YOUR RESPONSE EXACTLY AS FOLLOWS:

Score: X/10

Verdict:
[Correct / Partially Correct / Incorrect]

What was good:
- [Point 1]
- [Point 2]

What is missing or incorrect:
- [Point 1]
- [Point 2]

Specific Misconception:
[Write 1-2 sentences stating the exact technical misconception or gap, e.g. "Candidate mistakenly believed BFS uses a Stack instead of a Queue", or "None detected" if answer is correct]

How to improve:
- [Point 1]
- [Point 2]

Ideal Answer:
[Comprehensive, concise reference answer]

Follow-up Question:
[Concise follow-up question text without prefixes]
"""
    raw_eval = call_gemini(prompt)

    # Extract score and verdict
    score_match = re.search(r"Score:\s*(\d+(?:\.\d+)?)\s*/\s*10", raw_eval, re.IGNORECASE)
    verdict_match = re.search(r"Verdict:\s*\n*([^\n]+)", raw_eval, re.IGNORECASE)
    misconception_match = re.search(r"Specific Misconception:\s*\n*([^\n]+(?:\n[^\n]+)?)", raw_eval, re.IGNORECASE)
    follow_up_match = re.search(r"Follow-up Question:\s*\n*([^\n].*?)(?:\Z)", raw_eval, re.DOTALL | re.IGNORECASE)

    score_val = float(score_match.group(1)) if score_match else 5.0
    verdict_str = verdict_match.group(1).strip() if verdict_match else "Partially Correct"
    misconception_str = misconception_match.group(1).strip() if misconception_match else "None"
    follow_up_str = follow_up_match.group(1).strip() if follow_up_match else ""

    return {
        "raw_evaluation": raw_eval,
        "score": score_val,
        "verdict": verdict_str,
        "misconception": misconception_str,
        "follow_up_question": follow_up_str,
    }
