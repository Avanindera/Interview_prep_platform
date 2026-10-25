"""
=============================================================================
                    INTERVIEW QUESTION GENERATOR
=============================================================================
Compares material from multiple retrieved sources (Offline DB, GitHub,
GeeksforGeeks) and generates the highest-quality interview question.
=============================================================================
"""

import json
from typing import List, Dict, Any, Tuple
from app.rag.interviewer.gemini_client import call_gemini


def normalize_topic_query(query: str) -> str:
    """Corrects typos, abbreviations, and misspellings to standard CS topic names."""
    prompt = f"""You are a Computer Science search query normalizer.
Correct any typos, spelling errors, or informal abbreviations in the given technical query to its canonical standard technical topic name.
Example: 'DJKSTRA ALGORITHM' -> 'Dijkstra Algorithm'
Example: 'bsearch' -> 'Binary Search'
Example: 'bredth frst search' -> 'Breadth First Search (BFS)'
Example: 'link list' -> 'Linked List'

Query: {query}
Return ONLY the corrected topic name (no explanation, no punctuation, max 5 words):"""
    try:
        normalized = call_gemini(prompt).strip()
        # Strip any extra quotes
        normalized = normalized.strip('"\'')
        return normalized if len(normalized) >= 2 else query
    except Exception:
        return query


def generate_question_from_offline(topic: str, retrieved_results: List[Dict[str, Any]]) -> str:
    """Generates an interview question using retrieved offline database context."""
    context_blocks = []
    for i, res in enumerate(retrieved_results, start=1):
        chunk = res["chunk"]
        context_blocks.append(f"--- [OFFLINE CONTEXT {i}] Source: {chunk.get('source', 'offline')} ---\n{chunk.get('text', '')}")

    context_str = "\n\n".join(context_blocks)

    prompt = f"""You are a Principal Software Engineer and Senior Technical Interviewer.

INTERVIEW TOPIC:
{topic}

OFFLINE KNOWLEDGE BASE MATERIAL:
{context_str}

TASK:
1. Review the retrieved offline interview material above.
2. Formulate or select ONE clear, high-yield interview question suitable for a junior-to-mid level candidate / college student.
3. The question must test deep conceptual understanding (data structures, invariants, complexities, or edge cases).
4. Do NOT include the solution or answer in your output.
5. Return ONLY the interview question text directly, without conversational intros or formatting tags.
"""
    return call_gemini(prompt)


def compare_and_generate_best_question(topic: str, github_chunks: List[Dict[str, Any]], gfg_chunks: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    """
    Compares retrieved material from GitHub and GeeksforGeeks, performs source synthesis,
    and returns (best_question, ideal_answer, comparison_summary).
    """
    github_context = "\n\n".join([f"[GITHUB BLOCK {i+1} | {c.get('source', '')}]\n{c.get('text', '')}" for i, c in enumerate(github_chunks[:5])])
    gfg_context = "\n\n".join([f"[GEEKSFORGEEKS BLOCK {i+1} | {c.get('source', '')}]\n{c.get('text', '')}" for i, c in enumerate(gfg_chunks[:5])])

    prompt = f"""You are an elite technical interviewer comparing materials from two authoritative sources to design the ultimate interview question.

TOPIC / KEYWORD:
{topic}

--- SOURCE 1: GITHUB INTERVIEW REPOSITORY MATERIAL ---
{github_context or "No GitHub chunks retrieved."}

--- SOURCE 2: GEEKSFORGEEKS (GFG) ARTICLE & EXPLANATIONS ---
{gfg_context or "No GeeksforGeeks chunks retrieved."}

INSTRUCTIONS:
1. Cross-compare the technical nuances from both GitHub and GeeksforGeeks.
   - GitHub often provides practical code implementations and popular interview problem setups.
   - GeeksforGeeks provides rigorous algorithmic explanations, data structure invariants, and time/space complexity analysis.
2. Select or synthesize the SINGLE BEST interview question for this topic.
3. Provide a rigorous, concise Ideal Answer based on the combined sources.
4. Output your response as a valid JSON object matching this schema:

{{
  "comparison_summary": "Brief 2-sentence summary comparing what GitHub and GFG brought to the topic",
  "best_question": "The formulated interview question",
  "ideal_answer": "The comprehensive ideal answer covering data structure, mechanism, and complexities"
}}

IMPORTANT: Return ONLY the JSON object, with no markdown code fence wrappers or extra text.
"""
    raw_response = call_gemini(prompt)
    
    # Clean JSON
    cleaned = raw_response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        return (
            data.get("best_question", f"Explain the core mechanics and time/space complexity of {topic}."),
            data.get("ideal_answer", f"Detailed explanation of {topic}."),
            data.get("comparison_summary", "Compared repository code patterns with GeeksforGeeks algorithmic theory.")
        )
    except Exception:
        # Fallback if json parsing fails
        lines = [line.strip() for line in raw_response.splitlines() if line.strip()]
        q = lines[0] if lines else f"Explain the fundamental concepts and complexity of {topic}."
        return (q, "Ideal answer based on combined sources.", "Synthesized from GitHub and GeeksforGeeks.")
