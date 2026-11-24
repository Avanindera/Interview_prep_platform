"""
=============================================================================
                    AI SPEECH & DELIVERY EVALUATOR SERVICE
=============================================================================
Combines multimodal speech-to-text transcription with the new communication pipeline:
1. Dynamic KeyBERT Semantic Keyphrase Extraction (all-MiniLM-L6-v2) - replaces
   hardcoded dictionaries with dynamic cosine-similarity semantic scoring.
2. Linguistic Fluency & Disfluency Analysis (filler density, hedging phrases,
   lexical diversity / Type-Token Ratio).
3. Pre-trained Meta Model (StackingClassifier combining Logistic Regression,
   Random Forest, and WrappedXGBClassifier trained on 100,000 samples).
4. Academic benchmark metrics: Test Accuracy 88.24%, Precision 0.8782, Recall 0.8879,
   along with complete Confusion Matrix diagnostics.
5. High-fidelity Speech-to-Text Transcription via Google Gemini Multimodal Audio
   with local Whisper fallback.
=============================================================================
"""

import os
import re
import sys
import warnings
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

# Ensure models module is available for joblib unpickling WrappedXGBClassifier
try:
    from app.ml_models import models as ml_models_module
    sys.modules["models"] = ml_models_module
except Exception:
    try:
        from backend.app.ml_models import models as ml_models_module
        sys.modules["models"] = ml_models_module
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Linguistic Fluency Lexicons (Disfluency & Hesitation Markers)
# ---------------------------------------------------------------------------
FILLER_WORDS = [
    "um", "umm", "uh", "hmm", "ah", "like", "basically", "actually", "you know", "er"
]

HEDGING_PHRASES = [
    "maybe", "probably", "perhaps", "i think", "i guess", "sort of", "kind of", "not sure", "i suppose"
]

# Legacy technical keyword list retained for backward compatibility & fallback
TECHNICAL_KEYWORDS = [
    "api", "database", "sql", "nosql", "postgres", "postgresql", "mongodb", "redis",
    "cache", "caching", "latency", "throughput", "scalability", "scalable", "sharding",
    "microservice", "microservices", "kafka", "rabbitmq", "queue", "docker", "kubernetes",
    "container", "index", "indexes", "indexing", "concurrency", "thread", "threads",
    "asynchronous", "async", "load balancer", "load balancing", "failover", "replication",
    "acid", "idempotent", "idempotency", "rest", "graphql", "grpc", "ci/cd", "pipeline",
    "metric", "metrics", "prometheus", "grafana", "monitoring", "heap", "stack", "tree",
    "binary search", "dynamic programming", "hash", "algorithm", "complexity", "o(n)",
    "o(1)", "o(log n)", "o(n log n)", "transaction", "rollback", "deploy", "deployment",
    "opentelemetry", "tracing", "resilience", "circuit breaker", "rate limit", "token bucket",
    "bfs", "breadth first search", "dfs", "depth first search", "graph", "graphs",
    "vertex", "vertices", "edge", "edges", "node", "nodes"
]

# Benchmark metrics for the 100,000-sample trained Meta Model (Stacking)
MODEL_BENCHMARK_META = {
    "model_name": "Meta Model (Stacking)",
    "architecture": "StackingClassifier (LR + RF + WrappedXGBoost with LR Meta-Learner)",
    "training_samples": 100000,
    "test_accuracy": 88.24,
    "precision": 0.8782,
    "recall": 0.8879,
    "confusion_matrix": {
        "actual_good_pred_good": 8879,
        "actual_good_pred_needs_work": 1121,
        "actual_needs_work_pred_good": 1231,
        "actual_needs_work_pred_needs_work": 8769,
    },
}

# Lazy-loaded singletons
_classifier = None
_embedding_model = None
_keybert_model = None
_whisper_model = None


def get_model_path() -> Path:
    """Locates the serialized trained classifier checkpoint."""
    base_dir = Path(__file__).resolve().parent.parent
    local_path = base_dir / "ml_models" / "interview_classifier.pkl"
    if local_path.exists():
        return local_path
    
    # Check project-relative backend/app/ml_models
    alt_path = Path("backend/app/ml_models/interview_classifier.pkl")
    if alt_path.exists():
        return alt_path
        
    return local_path


def get_classifier():
    """Loads the trained Meta Model (Stacking) classifier."""
    global _classifier
    if _classifier is None:
        import joblib
        # Ensure 'models' is mapped for unpickling WrappedXGBClassifier
        try:
            from app.ml_models import models as ml_models_module
            sys.modules["models"] = ml_models_module
        except Exception:
            pass

        path = get_model_path()
        if path.exists():
            try:
                _classifier = joblib.load(path)
                print(f"[INFO] Speech Evaluator: Successfully loaded {type(_classifier).__name__} from {path}")
            except Exception as e:
                print(f"[WARN] Failed to load speech classifier from {path}: {e}")
    return _classifier


def get_embedding_model():
    """Loads the shared SentenceTransformer singleton for BERT embeddings."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[WARN] Failed to load SentenceTransformer for speech evaluator: {e}")
    return _embedding_model


def get_keybert_model():
    """Returns singleton KeyBERT model instance reusing the SentenceTransformer model."""
    global _keybert_model
    if _keybert_model is None:
        try:
            from keybert import KeyBERT
            emb = get_embedding_model()
            if emb is not None:
                _keybert_model = KeyBERT(model=emb)
            else:
                _keybert_model = KeyBERT(model="all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[WARN] Failed to initialize KeyBERT model: {e}")
    return _keybert_model


def get_whisper_model():
    """Lazy loader for local Whisper fallback."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            _whisper_model = whisper.load_model("base")
        except Exception:
            pass
    return _whisper_model


def extract_speech_features(
    text: str,
    top_n: int = 8,
    use_keybert: bool = True
) -> Dict[str, Any]:
    """
    Extract linguistic delivery features and dynamic BERT-based semantic keyphrases.
    
    Upgraded from static hardcoded keyword matching to KeyBERT:
    - Uses dense BERT embeddings (all-MiniLM-L6-v2) and cosine similarity ranking
      to dynamically discover the most topically salient 1-gram & 2-gram keyphrases.
    - Computes average KeyBERT relevance (Semantic Depth) reflecting technical substance.
    """
    text_lower = text.lower()
    words = re.findall(r"\b[\w']+\b", text_lower)
    total_words = len(words)

    # 1. Vocal Filler Words
    filler_words_found = [w for w in words if w in FILLER_WORDS]
    filler_count = len(filler_words_found)

    # 2. Hedging & Hesitation Markers
    hedging_phrases_found = [p for p in HEDGING_PHRASES if p in text_lower]
    hedging_count = sum(text_lower.count(p) for p in HEDGING_PHRASES)

    # 3. Disfluency Density (%)
    filler_density = round((filler_count / total_words * 100), 2) if total_words > 0 else 0.0
    hedging_density = round((hedging_count / total_words * 100), 2) if total_words > 0 else 0.0

    # 4. Dynamic KeyBERT Semantic Keyphrase Extraction
    keybert_results = []
    if use_keybert and total_words >= 3:
        try:
            kw_model = get_keybert_model()
            if kw_model is not None:
                keybert_results = kw_model.extract_keywords(
                    text,
                    keyphrase_ngram_range=(1, 2),
                    stop_words="english",
                    top_n=top_n
                )
        except Exception as e:
            print(f"[WARN] KeyBERT keyword extraction notice: {e}")
            keybert_results = []

    keybert_phrases = [kw for kw, _ in keybert_results]
    keybert_scores = {kw: round(float(score), 4) for kw, score in keybert_results}
    avg_keybert_relevance = (
        round(float(sum(score for _, score in keybert_results) / len(keybert_results)), 4)
        if keybert_results else 0.0
    )

    # 5. Technical Density based on KeyBERT
    keybert_keyword_count = len(keybert_phrases)
    keybert_density = round((keybert_keyword_count / total_words * 100), 2) if total_words > 0 else 0.0

    # 6. Lexical Diversity (Type-Token Ratio)
    lexical_diversity = round((len(set(words)) / total_words), 3) if total_words > 0 else 0.0

    # 7. Fallback keywords check if KeyBERT found nothing
    legacy_found = [
        kw for kw in TECHNICAL_KEYWORDS
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower)
    ]
    effective_tech_count = max(keybert_keyword_count, len(legacy_found))
    effective_tech_density = (
        round((effective_tech_count / total_words * 100), 2) if total_words > 0 else 0.0
    )

    return {
        "total_words": total_words,
        "filler_count": filler_count,
        "hedging_count": hedging_count,
        "filler_density": filler_density,
        "hedging_density": hedging_density,
        # KeyBERT dynamic extractions:
        "keybert_keywords": keybert_results,             # List of (phrase, score)
        "keybert_phrases": keybert_phrases,               # List of str
        "keybert_scores": keybert_scores,                 # Dict phrase -> score
        "avg_keybert_relevance": avg_keybert_relevance,   # Semantic Depth
        "semantic_depth": avg_keybert_relevance,
        "keybert_keyword_count": keybert_keyword_count,
        "keybert_density": keybert_density,
        # Backward compatibility aliases:
        "technical_keyword_count": effective_tech_count,
        "technical_keywords_found": keybert_phrases if keybert_phrases else legacy_found,
        "technical_density": effective_tech_density,
        "lexical_diversity": lexical_diversity,
        "filler_words_found": filler_words_found,
        "hedging_phrases_found": hedging_phrases_found,
    }


def _transcribe_with_speech_recognition(audio_path: str) -> str:
    """Fast, accurate, instant speech recognition via SpeechRecognition."""
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = r.record(source)
        text = r.recognize_google(audio_data)
        if text and len(text.strip()) > 0:
            return text.strip()
    except Exception as e:
        print(f"[WARN] SpeechRecognition note: {e}")
    return ""


def _transcribe_with_gemini(audio_path: str) -> str:
    """Accurate audio transcription using Gemini multimodal capabilities."""
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
    Transcribes an audio file (.wav, .mp3, .m4a, .webm, .ogg) with high accuracy and speed.
    1. Fast Primary: SpeechRecognition (instant, zero timeout, highly robust).
    2. Secondary: Gemini Multimodal Audio (high fidelity).
    3. Tertiary: Local Whisper model fallback.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    file_size = os.path.getsize(audio_path)
    if file_size < 100:
        print(f"[WARN] Audio file {audio_path} is too small ({file_size} bytes).")
        return ""

    # 1. Fast Primary: SpeechRecognition
    text = _transcribe_with_speech_recognition(audio_path)
    if text:
        return text

    # 2. Secondary: Gemini Multimodal Audio
    text = _transcribe_with_gemini(audio_path)
    if text:
        return text

    # 3. Tertiary fallback: Local Whisper
    text = _transcribe_with_whisper(audio_path)
    if text:
        return text

    return ""


def evaluate_speech_delivery(transcript: str) -> Dict[str, Any]:
    """
    Evaluates transcript speech delivery using the new AI-SpeechEvaluator pipeline:
    - KeyBERT Dynamic Semantic Keyphrase Extraction
    - Linguistic Disfluency & Hedging Analysis
    - Meta Model (StackingClassifier: LR + RF + XGBoost, 88.24% test accuracy)
    - Returns metrics, confidence, academic benchmark data, and coaching feedback.
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
            "keybert_keyphrases": [],
            "semantic_depth": 0.0,
            "model_benchmark": MODEL_BENCHMARK_META,
            "feedback": "No audible response detected. Please speak clearly into your microphone or provide a typed response.",
            "metrics": {},
        }

    # 1. Feature Extraction via KeyBERT and Linguistic Lexicons
    features = extract_speech_features(transcript_clean)
    total_words = features["total_words"]

    # 2. ML Model Prediction with the Meta Model (StackingClassifier)
    clf = get_classifier()
    emb_model = get_embedding_model()

    ml_verdict = "GOOD"
    raw_ml_confidence = 85.0

    if clf and emb_model and total_words >= 3:
        try:
            emb = emb_model.encode([transcript_clean], show_progress_bar=False, normalize_embeddings=True)
            pred = clf.predict(emb)[0]
            ml_verdict = "GOOD" if str(pred).lower() == "good" else "NEEDS_IMPROVEMENT"

            if hasattr(clf, "predict_proba"):
                probs = clf.predict_proba(emb)[0]
                class_idx = list(clf.classes_).index(pred)
                raw_ml_confidence = round(float(probs[class_idx] * 100), 1)
        except Exception as e:
            print(f"[WARN] Stacking Classifier prediction error: {e}")
            ml_verdict = "GOOD"

    # 3. Holistic Delivery Score Calibration (0 - 100%)
    if total_words < 5:
        calibrated_score = 25.0
        final_verdict = "NEEDS_IMPROVEMENT"
    else:
        score = 84.0

        # Disfluency & Filler Penalty/Bonus
        fd = features["filler_density"]
        if fd == 0.0 and total_words >= 20:
            score += 5.0
        elif fd <= 2.0:
            score += 2.0
        elif fd > 7.0:
            score -= 15.0
        elif fd > 4.0:
            score -= 8.0

        # Hedging Penalty
        hc = features["hedging_count"]
        if hc == 0 and total_words >= 20:
            score += 3.0
        elif hc >= 3:
            score -= 8.0
        elif hc >= 2:
            score -= 4.0

        # KeyBERT Semantic Depth Impact
        sem_depth = features["avg_keybert_relevance"]
        if sem_depth >= 0.40:
            score += 8.0
        elif sem_depth >= 0.30:
            score += 4.0
        elif sem_depth < 0.20 and total_words >= 30:
            score -= 6.0

        # ML Stacking Classifier Weighting
        if ml_verdict == "NEEDS_IMPROVEMENT":
            score -= 12.0
        else:
            score += 3.0

        calibrated_score = round(min(98.5, max(25.0, score)), 1)
        final_verdict = "GOOD" if calibrated_score >= 70.0 else "NEEDS_IMPROVEMENT"

    # 4. Tailored Coaching Recommendations
    coaching_tips: List[str] = []

    # Highlight KeyBERT extracted phrases
    if features["keybert_keywords"]:
        top_kws = [f"'{p}' ({s:.2f})" for p, s in features["keybert_keywords"][:4]]
        coaching_tips.append(
            f"KeyBERT dynamically identified core keyphrases: {', '.join(top_kws)} with a semantic depth of {features['avg_keybert_relevance']:.4f}."
        )

    if features["filler_density"] > 4.0:
        fillers_str = ", ".join(f"'{w}'" for w in list(set(features["filler_words_found"]))[:4])
        coaching_tips.append(
            f"Vocal filler density detected at {features['filler_density']}%. Replace fillers ({fillers_str}) with short deliberate pauses."
        )
    elif features["filler_count"] == 0 and total_words >= 20:
        coaching_tips.append("Excellent speech fluency! Zero vocal fillers detected in your spoken delivery.")

    if features["hedging_count"] >= 2:
        hedges_str = ", ".join(f"'{p}'" for p in list(set(features["hedging_phrases_found"]))[:3])
        coaching_tips.append(
            f"Detected hedging expressions ({hedges_str}). State your technical rationale with direct conviction."
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
        "keybert_keyphrases": features["keybert_keywords"],
        "semantic_depth": features["avg_keybert_relevance"],
        "model_benchmark": MODEL_BENCHMARK_META,
        "feedback": feedback_summary,
        "metrics": features,
    }
