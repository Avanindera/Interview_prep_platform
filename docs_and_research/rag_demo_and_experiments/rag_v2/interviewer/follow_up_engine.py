"""
=============================================================================
                    ADAPTIVE FOLLOW-UP QUESTION ENGINE
=============================================================================
Generates intelligent, adaptive follow-up questions tailored to:
1. Gaps / Misconceptions (if the candidate answers incorrectly or partially).
2. Advanced deep dives (if the candidate answers correctly).
Also evaluates multi-turn follow-up answers.
=============================================================================
"""

import re
from typing import Dict, Any, List, Optional
from rag_v2.interviewer.gemini_client import call_gemini


class FollowUpFeedback(str):
    """String subclass that preserves string compatibility while providing precomputed next follow-up."""
    def __new__(cls, feedback: str, next_follow_up: str = ""):
        obj = super().__new__(cls, feedback)
        obj.feedback = feedback
        obj.next_follow_up = next_follow_up
        return obj


def generate_adaptive_follow_up(
    topic: str,
    original_question: str,
    candidate_answer: str,
    evaluation: Dict[str, Any],
    reference_context: str
) -> str:
    """
    Generates a targeted follow-up question based on candidate's performance.
    If the candidate made an error / misconception (e.g. saying Stack instead of Queue for BFS),
    it directly probes that misconception (e.g. "Do you know what data structure (Stack vs Queue) is used in BFS and why?").
    """
    verdict = evaluation.get("verdict", "Partially Correct")
    score = evaluation.get("score", 5.0)
    misconception = evaluation.get("misconception", "None")

    prompt = f"""You are an empathetic yet rigorous Senior Technical Interviewer conducting a live interview.

TOPIC:
{topic}

PREVIOUS QUESTION:
{original_question}

CANDIDATE'S ANSWER:
{candidate_answer}

EVALUATION SUMMARY:
Score: {score}/10
Verdict: {verdict}
Identified Misconception / Gap: {misconception}

REFERENCE CONTEXT:
{reference_context}

INSTRUCTIONS FOR GENERATING FOLLOW-UP QUESTION:
1. If candidate's verdict is 'Incorrect' or 'Partially Correct' (or score < 7.5):
   - Focus specifically on their error or misconception.
   - For example: If they confused Stack with Queue in BFS, ask: "You mentioned using a stack. Do you know why a FIFO Queue is fundamentally required for BFS level-order traversal instead of a LIFO Stack, and what happens if a Stack is used?"
   - Help guide them to understand the foundational invariant they missed.
2. If candidate's verdict is 'Correct' (score >= 7.5):
   - Pose an advanced, real-world follow-up question (e.g., 0-1 BFS with Deque, bidirectional BFS, memory optimization, cycle detection, or handling large scale graphs).
3. Keep the follow-up concise, conversational, and direct.
4. Output ONLY the follow-up question text without prefixes like 'Interviewer:' or boilerplate.
"""
    return call_gemini(prompt)


def evaluate_follow_up_answer(
    topic: str,
    follow_up_question: str,
    candidate_answer: str,
    reference_context: str
) -> FollowUpFeedback:
    """
    Evaluates the candidate's answer to the follow-up question and proactively
    synthesizes the next follow-up probe to eliminate turn latency.
    """
    prompt = f"""You are a Senior Technical Interviewer evaluating a candidate's follow-up response.

TOPIC:
{topic}

FOLLOW-UP QUESTION:
{follow_up_question}

CANDIDATE'S RESPONSE:
{candidate_answer}

REFERENCE CONTEXT:
{reference_context}

FORMAT YOUR RESPONSE EXACTLY AS FOLLOWS:

Feedback:
1. State whether their understanding is now clear (Resolved / Partially Resolved / Still Needs Work).
2. Give a brief, constructive explanation of the correct concept.
3. Keep the feedback under 4 bullet points.

Next Follow-up Question:
[Write one deeper follow-up probe or edge case scenario on {topic}, or 'N/A' if thoroughly explored]
"""
    raw = call_gemini(prompt)

    next_match = re.search(r"Next Follow-up Question:\s*\n*([^\n].*?)(?:\Z)", raw, re.DOTALL | re.IGNORECASE)
    fb_match = re.search(r"Feedback:\s*(.*?)(?=(?:Next Follow-up Question|\Z))", raw, re.DOTALL | re.IGNORECASE)

    feedback_text = fb_match.group(1).strip() if fb_match else raw
    next_q = next_match.group(1).strip() if next_match else ""
    if next_q.lower() in {"n/a", "none", "n/a.", "none."}:
        next_q = ""

    return FollowUpFeedback(feedback_text, next_follow_up=next_q)
