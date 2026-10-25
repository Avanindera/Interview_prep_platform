"""
=============================================================================
                    GEMINI CLIENT & UTILITIES
=============================================================================
Manages Gemini API client initialization, model fallback, and robust retry
logic with exponential backoff.
=============================================================================
"""

import os
import sys
import time
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Ensure safe output encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env from rag_v2 or parent directory
load_dotenv()
parent_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
if os.path.exists(parent_env):
    load_dotenv(parent_env)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest"),
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.6-flash",
]

# Deduplicate model list while preserving order
FALLBACK_MODELS = list(dict.fromkeys([m for m in DEFAULT_MODELS if m]))
GEMINI_MODEL = FALLBACK_MODELS[0]

if not GEMINI_API_KEY:
    print("\n[ERROR] GEMINI_API_KEY not found in environment or .env!")
    print("Please set GEMINI_API_KEY in your .env file.\n")


def get_gemini_client() -> genai.Client:
    """Returns an initialized Google GenAI client."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=GEMINI_API_KEY)


def call_gemini(prompt: str, model_name: Optional[str] = None, max_retries: int = 3, initial_delay: float = 1.0) -> str:
    """
    Invokes Gemini API with clean config (AFC disabled), automatic model fallback,
    and exponential backoff for temporary rate limits / high demand.
    """
    client = get_gemini_client()
    models_to_try = [model_name] if model_name else FALLBACK_MODELS
    config = types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )

    last_exc = None

    for m_name in models_to_try:
        delay = initial_delay
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=m_name,
                    contents=prompt,
                    config=config,
                )
                if response and response.text:
                    return response.text.strip()
                raise RuntimeError("Empty text received from Gemini API.")
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                # Fast fallback on rate limit, 404, or 503 high demand
                if (
                    "resource_exhausted" in err_str
                    or "429" in err_str
                    or "quota" in err_str
                    or "404" in err_str
                    or "not found" in err_str
                    or "503" in err_str
                    or "unavailable" in err_str
                    or "high demand" in err_str
                ):
                    break
                if attempt == max_retries:
                    break
                print(f"\n  [WARN] Gemini API notice on '{m_name}' (attempt {attempt}/{max_retries}): {exc}")
                print(f"         Retrying in {delay:.1f}s...")
                time.sleep(delay)
                delay *= 1.5

    raise RuntimeError(f"All Gemini models failed: {last_exc}")
