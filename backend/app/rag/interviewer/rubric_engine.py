"""
=============================================================================
                    GRADUAL RUBRIC & ADAPTIVE INTERVIEW ENGINE
=============================================================================
Defines the pedagogical rubric difficulty ladder for technical interviews:
  Level 1 (BASIC / EASY):   Foundational Concepts, Definition & Core Intuition.
  Level 2 (MEDIUM):         Algorithmic Mechanics, State Tracking & Invariants, Big-O Complexity.
                            (Adjusted to EASY-MEDIUM GUIDED if candidate struggled in Round 1)
  Level 3 (ADVANCED):       Edge Cases, Boundary Conditions & Algorithmic Variations.
                            (Adjusted to MEDIUM if candidate struggled in Round 2)
  Level 4 (HARD):           Real-World Applied Scenarios, System Scale & Optimizations.
  Level 5 (EXPERT):         Deep Architectural Trade-offs, Memory Constraints & System Design.

Ensures:
1. Every interview STARTS GRADUAL (Level 1: Basic / Easy) - never leaping to complex scenarios upfront.
2. The ENTIRE INTERVIEW IS DYNAMICALLY ADAPTIVE - every subsequent question
   specifically adjusts its difficulty level and focus based on the student's previous response,
   score, and misconceptions.
=============================================================================
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from app.rag.interviewer.gemini_client import call_gemini


RUBRIC_STAGES: Dict[int, Dict[str, str]] = {
    1: {
        "level_name": "Level 1: Basic / Foundational Intuition",
        "difficulty": "BASIC / EASY",
        "goal": (
            "Assess basic conceptual familiarity and mental model. "
            "Ask for core definition, high-level intuition, and the fundamental data structure used. "
            "Do NOT ask for tricky edge cases, complex variations, or distributed scale here. Keep it gentle and accessible."
        ),
        "fallback_template": (
            "Let's start with the foundational intuition behind {topic}. "
            "In simple terms, how would you define {topic}, what is the core intuition behind how it works, "
            "and which primary data structure is essential for its operation and why?"
        ),
    },
    2: {
        "level_name": "Level 2: Implementation Mechanics, Invariants & Complexity",
        "difficulty": "MEDIUM",
        "goal": (
            "Assess concrete implementation invariants, state tracking (e.g. visited tracking to prevent cycles), "
            "and formal asymptotic Time and Space complexities. "
            "Crucially, adapt to the candidate's previous response: if they missed an invariant or held a misconception, "
            "gently guide or probe them on that principle."
        ),
        "fallback_template": (
            "Moving to implementation mechanics for {topic}: how do you track state (such as visited elements or base cases) "
            "to prevent infinite loops or redundant work? What are the exact Big-O Time and Space complexities, and how do they depend on the input size?"
        ),
    },
    3: {
        "level_name": "Level 3: Edge Cases, Boundary Conditions & Variations",
        "difficulty": "ADVANCED",
        "goal": (
            "Assess handling of tricky boundary conditions (empty inputs, disconnected graphs/components, single elements, cycles) "
            "and algorithmic variations (e.g. 0-1 variations, bidirectional search, alternative data structures). "
            "Adapt to the candidate's strengths or gaps demonstrated in rounds 1 and 2."
        ),
        "fallback_template": (
            "Now let's examine edge cases and variations in {topic}. What edge cases or unusual inputs can break a standard implementation "
            "(e.g., disconnected components, cyclic structures, or special weights/constraints), and what variation or adaptation would you use to handle them?"
        ),
    },
    4: {
        "level_name": "Level 4: Real-World Applied Scenarios & Optimizations",
        "difficulty": "HARD",
        "goal": (
            "Assess applied problem solving and practical engineering trade-offs under constraints "
            "(e.g. finding shortest paths in massive networks, word ladders, memory-bounded search, pruning). "
            "Challenge the candidate to optimize runtime and memory when scaling up."
        ),
        "fallback_template": (
            "In practical applications of {topic} at large scale (such as social networks or routing graphs with large branching factors), "
            "standard approaches can face severe memory or latency bottlenecks. How would you optimize the search, prune unneeded states, or apply techniques like bidirectional search?"
        ),
    },
    5: {
        "level_name": "Level 5: Deep Architectural Trade-offs & System Scale",
        "difficulty": "EXPERT",
        "goal": (
            "Assess architectural synthesis and deep comparisons (e.g. BFS vs DFS memory footprints under deep vs wide graphs, "
            "iterative vs recursive considerations, external memory / disk-backed queues when data exceeds RAM). "
            "Final capstone evaluation."
        ),
        "fallback_template": (
            "For a deep architectural comparison on {topic}: how do its memory footprint and traversal dynamics compare to alternative approaches "
            "when processing deep versus wide graphs? If the dataset has billions of entries exceeding available physical RAM, how would you design an external-memory solution?"
        ),
    },
}


def get_rubric_stage(order: int, total_questions: int = 3) -> Dict[str, str]:
    """
    Maps an interview question order (1, 2, 3...) to its corresponding baseline rubric stage.
    """
    total = max(1, min(total_questions, 5))
    order_clamped = max(1, min(order, total))

    if total == 1:
        stage_idx = 1
    elif total == 2:
        stage_idx = 1 if order_clamped == 1 else 2
    elif total == 3:
        stage_idx = order_clamped
    elif total == 4:
        stage_idx = order_clamped
    else:
        stage_idx = order_clamped

    return RUBRIC_STAGES.get(stage_idx, RUBRIC_STAGES[min(order_clamped, 5)])


def generate_initial_rubric_question(topic: str, reference_context: str) -> Tuple[str, str]:
    """
    Generates Question 1 following Rubric Level 1: Basic / Foundational Intuition (BASIC / EASY).
    Ensures the interview starts gentle, accessible, and structured.
    """
    stage = RUBRIC_STAGES[1]
    prompt = f"""You are an encouraging, expert Senior Technical Interviewer conducting the FIRST round of a live interview.

INTERVIEW TOPIC: {topic}
ROUND: Question 1 (Foundational / Conceptual)
TARGET DIFFICULTY: BASIC / EASY
PEDAGOGICAL GOAL:
Assess basic conceptual familiarity and mental model. Ask for core definition, high-level intuition, and the fundamental data structure used.
Do NOT ask for tricky edge cases, complex variations, or distributed scale here. Keep it gentle, accessible, and confidence-building.

RETRIEVED TECHNICAL GROUND TRUTH:
{reference_context[:2000] if reference_context else f"Topic: {topic}"}

CRITICAL RULES FOR QUESTION 1:
1. START GRADUAL (BASIC / EASY): Ask ONE clear, gentle conceptual question.
2. Focus strictly on:
   - What {topic} is in simple terms.
   - The basic intuition of how it operates.
   - The core data structure that powers it and why that data structure makes sense.
3. Do NOT ask for multi-part edge cases, asymptotic proofs, or complex distributed trade-offs in this first question.
4. Keep the wording warm, conversational, and direct as an interviewer speaking to a candidate.
5. Output ONLY the question text. Do NOT include greetings, prefixes like 'Q1:' or 'Interviewer:', and do NOT include the answer.
"""
    try:
        raw = call_gemini(prompt).strip()
        cleaned = re.sub(r"^(?:Question\s*\d*[:\.\-]?|Q\d*[:\.\-]?|Interviewer[:\.\-]?)\s*", "", raw, flags=re.IGNORECASE).strip()
        cleaned = cleaned.strip('"\'')
        if len(cleaned) > 20:
            return cleaned, stage["difficulty"]
    except Exception as e:
        print(f"[WARN] Error generating initial rubric question: {e}")

    fallback = stage["fallback_template"].format(topic=topic)
    return fallback, stage["difficulty"]


def generate_adaptive_next_question(
    topic: str,
    target_order: int,
    total_questions: int,
    interview_history: List[Dict[str, Any]],
    reference_context: str,
) -> Tuple[str, str]:
    """
    Generates the next question in the interview (Question 2, 3, etc.) adaptively.
    Dynamically adjusts the difficulty level based on candidate's previous response and score:
    - If candidate performed well (score >= 7.0): increases difficulty along the ladder (Basic -> Medium -> Advanced).
    - If candidate struggled or had misconceptions (score < 7.0): adjusts difficulty to a supportive/guided level
      specifically probing the misconception before advancing.
    
    Returns:
    - (question_text, adjusted_difficulty)
    """
    stage = get_rubric_stage(target_order, total_questions)

    # Format previous rounds history for prompt context
    history_blocks = []
    for h in interview_history:
        ord_num = h.get("order", 1)
        q_text = h.get("question", "")
        a_text = h.get("candidate_answer", "")
        score = h.get("technical_score", "N/A")
        verdict = h.get("technical_verdict", "N/A")
        misconception = h.get("misconception", "None")

        block = (
            f"--- ROUND {ord_num} ---\n"
            f"Question Asked: {q_text}\n"
            f"Candidate's Answer: {a_text}\n"
            f"Evaluation: Score {score}/10, Verdict: {verdict}\n"
            f"Identified Misconception / Gap: {misconception}\n"
        )
        history_blocks.append(block)

    history_str = "\n".join(history_blocks) if history_blocks else "No previous history."
    latest_round = interview_history[-1] if interview_history else {}
    latest_score = latest_round.get("technical_score", 5.0) or 5.0
    latest_misconception = latest_round.get("misconception", "None")
    latest_verdict = latest_round.get("technical_verdict", "Partially Correct")

    # DYNAMIC LEVEL ADJUSTMENT:
    if target_order == 2:
        if latest_score >= 7.0:
            target_diff = "MEDIUM"
            guidance = "The candidate demonstrated solid basic understanding in Round 1. Advance the difficulty to MEDIUM: test algorithmic mechanics, state tracking (visited array/set to prevent cycles), and Big-O Time & Space complexities."
        else:
            target_diff = "EASY-MEDIUM (GUIDED)"
            guidance = f"The candidate showed gaps/misconceptions in Round 1 ({latest_misconception}). Adjust difficulty to EASY-MEDIUM (supportive/guided): guide or probe them directly on the invariant they missed before advancing to complex mechanics."
    elif target_order >= 3:
        if latest_score >= 7.5:
            target_diff = "ADVANCED"
            guidance = "The candidate answered previous implementation mechanics accurately. Elevate difficulty to ADVANCED: test tricky edge cases (e.g. disconnected graphs, weighted vs unweighted), algorithmic variations (0-1 variations, bidirectional search), or system scale."
        else:
            target_diff = "MEDIUM"
            guidance = f"The candidate had difficulty with previous mechanics ({latest_misconception}). Keep difficulty at MEDIUM: ask a clear, structured question testing edge cases simply, reinforcing foundational invariants."
    else:
        target_diff = stage["difficulty"]
        guidance = stage["goal"]

    prompt = f"""You are a distinguished Senior Technical Interviewer conducting an adaptive, gradual technical interview.

INTERVIEW TOPIC: {topic}
CURRENT ROUND TO GENERATE: Question {target_order} of {total_questions}
ADJUSTED DIFFICULTY: {target_diff}
STAGE PEDAGOGICAL GOAL:
{guidance}

RETRIEVED TECHNICAL GROUND TRUTH:
{reference_context[:2200] if reference_context else f"Topic: {topic}"}

CANDIDATE'S PERFORMANCE HISTORY SO FAR:
{history_str}

LATEST OBSERVATION (Round {target_order - 1}):
- Score: {latest_score}/10
- Verdict: {latest_verdict}
- Identified Misconceptions / Gaps: {latest_misconception}

ADAPTIVE QUESTION FORMULATION INSTRUCTIONS:
1. GRADUAL FLOW & ADJUSTED DIFFICULTY: Formulate the question strictly at difficulty level '{target_diff}'.
2. ADAPTIVE TO CANDIDATE'S PREVIOUS RESPONSE:
   - If the candidate had a misconception, factual error, or incomplete reasoning in their previous response:
     Smoothly integrate that observation into the new question. For example: "In your previous response, you touched upon X. In the context of {target_diff}, how does Y resolve this invariant and why?"
   - If the candidate answered strongly and accurately:
     Acknowledge their solid foundation and challenge them with a deeper invariant or nuanced scenario appropriate for {target_diff}.
3. CONVERSATIONAL & PROFESSIONAL: Speak directly to the candidate like an interviewer on a live call.
4. Output ONLY the question text. Do NOT include greetings, prefixes like 'Question {target_order}:', or solutions.
"""
    try:
        raw = call_gemini(prompt).strip()
        cleaned = re.sub(r"^(?:Question\s*\d*[:\.\-]?|Q\d*[:\.\-]?|Interviewer[:\.\-]?)\s*", "", raw, flags=re.IGNORECASE).strip()
        cleaned = cleaned.strip('"\'')
        if len(cleaned) > 20:
            return cleaned, target_diff
    except Exception as e:
        print(f"[WARN] Error generating adaptive next question for round {target_order}: {e}")

    # Fallback tailored to stage
    fallback = stage["fallback_template"].format(topic=topic)
    return fallback, target_diff
