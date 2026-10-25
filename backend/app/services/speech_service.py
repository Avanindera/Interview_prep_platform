"""
=============================================================================
                    AI SPEECH & DELIVERY EVALUATOR SERVICE
=============================================================================
Combines multimodal speech-to-text transcription with:
1. Linguistic feature extraction (filler density, hedging phrases, lexical diversity).
2. Technical vocabulary density analysis.
3. Pre-trained Machine Learning Classifier (interview_classifier.pkl).
4. Tailored coaching feedback on verbal delivery, pacing, and confidence.
=============================================================================
"""

import os
import re
import warnings
from pathlib import Path
from typing import Dict, Any, Optional, List

warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# Linguistic Lexicons
# ---------------------------------------------------------------------------
FILLER_WORDS = [
    "um", "umm", "uh", "hmm", "ah", "like", "basically", "actually", "you know", "er"
]

HEDGING_PHRASES = [
    "maybe", "probably", "perhaps", "i think", "i guess", "sort of", "kind of", "not sure", "i suppose"
]

TECHNICAL_KEYWORDS = [
    # Data Structures & Algorithms
    "bfs", "breadth first search", "dfs", "depth first search", "graph", "graphs",
    "vertex", "vertices", "edge", "edges", "node", "nodes", "queue", "priority queue",
    "stack", "deque", "heap", "min heap", "max heap", "tree", "binary tree", "bst",
    "binary search", "shortest path", "dijkstra", "bellman-ford", "floyd-warshall",
    "topological sort", "cycle", "dag", "unweighted", "weighted", "visited",
    "adjacency list", "adjacency matrix", "hash map", "hash table", "hash",
    "array", "linked list", "dynamic programming", "memoization", "recursion",
    "greedy", "backtracking", "two pointers", "sliding window", "divide and conquer",
    "time complexity", "space complexity", "complexity", "big-o", "o(n)", "o(1)",
    "o(log n)", "o(n log n)", "o(v + e)", "asymptotic", "in-degree", "out-degree",
    # System Architecture, Backend & Concurrency
    "api", "database", "sql", "nosql", "postgres", "postgresql", "mongodb", "redis",
    "cache", "caching", "latency", "throughput", "scalability", "scalable", "sharding",
    "microservice", "microservices", "kafka", "rabbitmq", "docker", "kubernetes",
    "container", "index", "indexes", "indexing", "concurrency", "thread", "threads",
    "asynchronous", "async", "load balancer", "load balancing", "failover", "replication",
    "acid", "idempotent", "idempotency", "rest", "graphql", "grpc", "ci/cd", "pipeline",
    "metric", "metrics", "prometheus", "grafana", "monitoring", "transaction", "rollback",
    "deploy", "deployment", "opentelemetry", "tracing", "resilience", "circuit breaker",
    "rate limit", "token bucket"
]

# Lazy-loaded singletons
_classifier = None
_embedding_model = None
_whisper_model = None


def get_model_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    local_path = base_dir / "ml_models" / "interview_classifier.pkl"
    if local_path.exists():
        return local_path
    ext_path = Path("C:/Users/aryan/Downloads/AI_Speech_Evaluator/AI_Speech_Evaluator/interview_classifier.pkl")
    if ext_path.exists():
        return ext_path
    return local_path


def get_classifier():
    global _classifier
    if _classifier is None:
        import joblib
        path = get_model_path()
        if path.exists():
            try:
                _classifier = joblib.load(path)
            except Exception as e:
                print(f"[WARN] Failed to load speech classifier from {path}: {e}")
    return _classifier


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[WARN] Failed to load SentenceTransformer for speech evaluator: {e}")
    return _embedding_model


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            _whisper_model = whisper.load_model("base")
        except Exception as e:
            # Whisper is optional since Gemini multimodal transcription is the primary engine
            pass
    return _whisper_model


def extract_speech_features(text: str) -> Dict[str, Any]:
    """Extract linguistic, fluency, and technical depth features from a transcript."""
    text_lower = text.lower()
    words = re.findall(r"\b[\w']+\b", text_lower)
    total_words = len(words)

    # 1. Fillers
    filler_words_found = [w for w in words if w in FILLER_WORDS]
    filler_count = len(filler_words_found)

    # 2. Hedging
    hedging_phrases_found = [p for p in HEDGING_PHRASES if p in text_lower]
    hedging_count = sum(text_lower.count(p) for p in HEDGING_PHRASES)

    # 3. Densities
    filler_density = round((filler_count / total_words * 100), 2) if total_words > 0 else 0.0
    hedging_density = round((hedging_count / total_words * 100), 2) if total_words > 0 else 0.0

    # 4. Technical Keywords (detect single words or multi-word terms)
    technical_keywords_found = [
        kw for kw in TECHNICAL_KEYWORDS
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower)
    ]
    technical_keyword_count = len(technical_keywords_found)
    technical_density = round((technical_keyword_count / total_words * 100), 2) if total_words > 0 else 0.0

    # 5. Lexical Diversity (Type-Token Ratio)
    lexical_diversity = round((len(set(words)) / total_words), 3) if total_words > 0 else 0.0

    return {
        "total_words": total_words,
        "filler_count": filler_count,
        "hedging_count": hedging_count,
        "filler_density": filler_density,
        "hedging_density": hedging_density,
        "technical_keyword_count": technical_keyword_count,
        "technical_density": technical_density,
        "lexical_diversity": lexical_diversity,
        "filler_words_found": filler_words_found,
        "hedging_phrases_found": hedging_phrases_found,
        "technical_keywords_found": technical_keywords_found,
    }


def _transcribe_with_gemini(audio_path: str) -> str:
    """Fast, accurate audio transcription using Gemini multimodal capabilities."""
    try:
        from app.rag.interviewer.gemini_client import get_gemini_client, FALLBACK_MODELS
        from google.genai import types

        ext = Path(audio_path).suffix.lower()
        mime_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mp3",
            ".m4a": "audio/m4a",
            ".ogg": "audio/ogg",
            ".webm": "audio/webm",
            ".flac": "audio/flac",
        }
        mime_type = mime_map.get(ext, "audio/wav")

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        if not audio_bytes or len(audio_bytes) < 100:
            return ""

        client = get_gemini_client()
        part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        prompt = (
            "You are a verbatim speech-to-text transcriber for a live technical interview. "
            "Please accurately transcribe this candidate spoken audio into plain text. "
            "Preserve verbal hesitation words like um, uh, ah, like if spoken. "
            "Accurately capture technical engineering vocabulary and algorithmic terms. "
            "Return ONLY the verbatim transcript as plain text with no added commentary or markdown fences."
        )

        config = types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.1,
        )

        for m_name in FALLBACK_MODELS:
            try:
                response = client.models.generate_content(
                    model=m_name,
                    contents=[part, prompt],
                    config=config,
                )
                if response and response.text:
                    cleaned = response.text.strip()
                    cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
                    cleaned = re.sub(r"\n?```$", "", cleaned)
                    return cleaned.strip()
            except Exception as ex:
                err_str = str(ex).lower()
                print(f"[WARN] Gemini transcription attempt with model {m_name} failed: {ex}")
                if any(x in err_str for x in ["resource_exhausted", "429", "quota", "503"]):
                    continue
                continue
    except Exception as e:
        print(f"[WARN] Gemini audio transcription error: {e}")

    return ""


def _transcribe_with_whisper(audio_path: str) -> str:
    """Fallback transcription with local Whisper if available."""
    try:
        model = get_whisper_model()
        if model:
            result = model.transcribe(audio_path, fp16=False)
            return result.get("text", "").strip()
    except Exception as e:
        print(f"[WARN] Whisper fallback transcription error: {e}")
    return ""


def transcribe_audio_file(audio_path: str) -> str:
    """
    Transcribes an audio file (.wav, .mp3, .m4a, .webm, .ogg) with high accuracy.
    Primary: Gemini Multimodal Audio API (high fidelity, captures fillers & tech terms).
    Fallback: Local Whisper model (if available).
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    file_size = os.path.getsize(audio_path)
    if file_size < 100:
        print(f"[WARN] Audio file {audio_path} is too small ({file_size} bytes).")
        return ""

    # Primary: Gemini Multimodal Audio Transcription
    transcript = _transcribe_with_gemini(audio_path)
    if transcript:
        return transcript

    # Secondary fallback: Local Whisper
    transcript = _transcribe_with_whisper(audio_path)
    if transcript:
        return transcript

    return ""


def evaluate_speech_delivery(transcript: str) -> Dict[str, Any]:
    """
    Evaluates transcript speech delivery characteristics and runs ML classification.
    Returns dictionary with metrics, classification verdict, confidence score, and coaching feedback.
    """
    transcript_clean = transcript.strip()
    if not transcript_clean or transcript_clean.lower() in ["no response provided.", "no audible response detected."]:
        return {
            "verdict": "NEEDS_IMPROVEMENT",
            "confidence": 0.0,
            "total_words": 0,
            "filler_count": 0,
            "filler_density": 0.0,
            "hedging_count": 0,
            "technical_keyword_count": 0,
            "technical_density": 0.0,
            "lexical_diversity": 0.0,
            "feedback": "No audible response detected. Please speak clearly into your microphone or provide a typed response.",
            "metrics": {},
        }

    features = extract_speech_features(transcript_clean)
    total_words = features["total_words"]

    # ML Model Prediction
    clf = get_classifier()
    emb_model = get_embedding_model()

    ml_verdict = "GOOD"
    raw_ml_confidence = 80.0

    if clf and emb_model and total_words >= 5:
        try:
            emb = emb_model.encode([transcript_clean], show_progress_bar=False, normalize_embeddings=True)
            pred = clf.predict(emb)[0]
            ml_verdict = "GOOD" if str(pred).lower() == "good" else "NEEDS_IMPROVEMENT"

            if hasattr(clf, "predict_proba"):
                probs = clf.predict_proba(emb)[0]
                class_idx = list(clf.classes_).index(pred)
                raw_ml_confidence = round(float(probs[class_idx] * 100), 1)
        except Exception as e:
            print(f"[WARN] Speech classification error: {e}")
            ml_verdict = "GOOD"

    # Holistic Delivery Score & Calibrated Confidence (0 - 100%)
    # Factors: Linguistic fluency (fillers), technical articulation, hedging, and sentence cohesion
    if total_words < 5:
        calibrated_score = 25.0
        final_verdict = "NEEDS_IMPROVEMENT"
    else:
        score = 82.0

        # 1. Fluency & Filler density impact
        fd = features["filler_density"]
        if fd == 0.0 and total_words >= 20:
            score += 6.0
        elif fd <= 2.0:
            score += 2.0
        elif fd > 7.0:
            score -= 15.0
        elif fd > 4.0:
            score -= 8.0

        # 2. Technical Vocabulary Impact
        tk_count = features["technical_keyword_count"]
        if tk_count >= 4:
            score += 8.0
        elif tk_count >= 2:
            score += 5.0
        elif total_words >= 30 and tk_count == 0:
            score -= 8.0

        # 3. Directness & Hedging Impact
        hc = features["hedging_count"]
        if hc == 0 and total_words >= 20:
            score += 3.0
        elif hc >= 3:
            score -= 8.0
        elif hc >= 2:
            score -= 4.0

        # 4. ML Model factor
        if ml_verdict == "NEEDS_IMPROVEMENT":
            score -= 10.0
        else:
            score += 2.0

        calibrated_score = round(min(98.0, max(30.0, score)), 1)
        final_verdict = "GOOD" if calibrated_score >= 70.0 else "NEEDS_IMPROVEMENT"

    # Tailored coaching recommendations
    coaching_tips: List[str] = []

    if features["filler_density"] > 4.0:
        fillers_str = ", ".join(f"'{w}'" for w in list(set(features["filler_words_found"]))[:4])
        coaching_tips.append(
            f"Vocal filler density detected at {features['filler_density']}%. Substitute fillers ({fillers_str}) with deliberate brief pauses."
        )
    elif features["filler_count"] == 0 and total_words >= 20:
        coaching_tips.append("Excellent speech fluency! Zero vocal fillers detected in your spoken delivery.")

    if features["hedging_count"] >= 2:
        hedges_str = ", ".join(f"'{p}'" for p in list(set(features["hedging_phrases_found"]))[:3])
        coaching_tips.append(
            f"Detected hedging expressions ({hedges_str}). State your technical rationale with direct conviction."
        )

    if features["technical_keyword_count"] >= 3:
        sample_terms = ", ".join(features["technical_keywords_found"][:4])
        coaching_tips.append(
            f"Strong engineering vocabulary ({features['technical_keyword_count']} technical terms: {sample_terms})."
        )
    elif total_words >= 25 and features["technical_keyword_count"] < 2:
        coaching_tips.append(
            "Enrich your response with specific engineering keywords (e.g., invariants, data structures, complexity bounds)."
        )

    if not coaching_tips:
        if final_verdict == "GOOD":
            coaching_tips.append("Clear, articulate, and well-paced delivery with strong technical framing.")
        else:
            coaching_tips.append("Delivery can be improved with higher technical specificity and smoother pacing.")

    feedback_summary = " ".join(coaching_tips)

    return {
        "verdict": final_verdict,
        "confidence": calibrated_score,
        "total_words": total_words,
        "filler_count": features["filler_count"],
        "filler_density": features["filler_density"],
        "hedging_count": features["hedging_count"],
        "technical_keyword_count": features["technical_keyword_count"],
        "technical_density": features["technical_density"],
        "lexical_diversity": features["lexical_diversity"],
        "feedback": feedback_summary,
        "metrics": features,
    }
