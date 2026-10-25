"""
=============================================================================
             AI-POWERED INTERVIEW RAG PIPELINE (DYNAMIC GITHUB SOURCE)
=============================================================================
Architecture:
  USER QUERY
      ↓
  GITHUB REPOSITORY SEARCH & QUERY EXPANSION
      ↓
  BEST INTERVIEW REPOSITORY RANKING & SELECTION
      ↓
  LOCAL CACHING & CONTENT EXTRACTION (.md, .txt, .json, .csv)
      ↓
  CHUNKING (Overlap Chunks)
      ↓
  SENTENCE-TRANSFORMERS EMBEDDINGS (all-MiniLM-L6-v2)
      ↓
  FAISS VECTOR INDEX (faiss.IndexFlatIP + L2 Normalization)
      ↓
  SEMANTIC SEARCH (Top-K Chunks)
      ↓
  GEMINI 2.5/3.6 FLASH (Question Generation strictly from retrieved context)
      ↓
  CANDIDATE ANSWER SUBMISSION
      ↓
  GEMINI EVALUATION (Score /10, Verdict, Good, Missing, Improvement, Ideal Answer)
=============================================================================
"""

import os
import sys
import re
import io
import json
import csv
import zipfile
import math
from pathlib import Path
from urllib.parse import quote

import requests
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from google import genai
from google.genai import types
from dotenv import load_dotenv
import time

# Force UTF-8 encoding on standard output for Windows console compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_CACHE_DIR = os.path.join(BASE_DIR, "repo_cache")

TOP_K = 5
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

if not GEMINI_API_KEY:
    print("\n[ERROR] GEMINI_API_KEY not found in .env file!")
    print("Please add your key to .env: GEMINI_API_KEY=your_key_here\n")
    sys.exit(1)

# Initialize Gemini Client
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def get_github_headers():
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-Interview-RAG-App",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


# ============================================================
# STEP 1 — GITHUB REPOSITORY SEARCH & DISCOVERY
# ============================================================

def generate_search_queries(topic: str) -> list[str]:
    """Generate search query variations for GitHub API."""
    topic_clean = topic.strip()
    return [
        f"{topic_clean} interview questions",
        f"{topic_clean} coding interview",
        f"{topic_clean} technical interview",
        f"{topic_clean} interview preparation",
        f"data structures algorithms {topic_clean}",
    ]


def search_github_repositories(topic: str, max_candidates: int = 15) -> list[dict]:
    """
    Search GitHub API dynamically for interview repositories matching the topic.
    Returns ranked repository metadata.
    """
    queries = generate_search_queries(topic)
    headers = get_github_headers()
    candidates = {}

    for q in queries[:3]:
        url = f"https://api.github.com/search/repositories?q={quote(q)}&sort=stars&order=desc&per_page=10"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 403 or resp.status_code == 429:
                print("  ⚠️ GitHub API rate limit reached.")
                break
            if resp.status_code != 200:
                continue

            data = resp.json()
            items = data.get("items", [])
            for item in items:
                repo_id = item["full_name"]
                if repo_id not in candidates:
                    candidates[repo_id] = {
                        "full_name": item["full_name"],
                        "name": item["name"],
                        "owner": item["owner"]["login"],
                        "description": item.get("description") or "",
                        "stars": item.get("stargazers_count", 0),
                        "forks": item.get("forks_count", 0),
                        "url": item.get("html_url", ""),
                        "default_branch": item.get("default_branch", "main"),
                    }
        except requests.RequestException as exc:
            print(f"  ⚠️ Error searching GitHub for '{q}': {exc}")
            continue

    if not candidates:
        return []

    # Score and rank candidates
    ranked = []
    topic_words = set(re.findall(r"\w+", topic.lower()))
    interview_keywords = {"interview", "questions", "answers", "prep", "coding", "technical", "algo", "ds", "awesome", "guide"}

    for repo in candidates.values():
        desc_lower = (repo["name"] + " " + repo["description"]).lower()
        desc_words = set(re.findall(r"\w+", desc_lower))

        topic_matches = len(topic_words.intersection(desc_words))
        interview_matches = len(interview_keywords.intersection(desc_words))

        # Log star score calculation
        star_score = math.log10(repo["stars"] + 1) * 2
        relevance_score = (topic_matches * 3.0) + (interview_matches * 2.0) + star_score

        repo_copy = dict(repo)
        repo_copy["relevance_score"] = round(relevance_score, 2)
        ranked.append(repo_copy)

    ranked.sort(key=lambda x: x["relevance_score"], reverse=True)
    return ranked[:max_candidates]


# ============================================================
# STEP 2 — REPOSITORY DOWNLOAD & CACHING
# ============================================================

def download_and_cache_repo(repo: dict) -> str:
    """
    Downloads repository ZIP archive from GitHub and extracts it to repo_cache/.
    If already cached, returns cached folder path immediately.
    """
    os.makedirs(REPO_CACHE_DIR, exist_ok=True)
    safe_folder_name = repo["full_name"].replace("/", "_")
    target_dir = os.path.join(REPO_CACHE_DIR, safe_folder_name)

    # Check cache
    if os.path.exists(target_dir) and os.listdir(target_dir):
        print(f"  ✓ Found cached repository at: repo_cache/{safe_folder_name}")
        return target_dir

    print(f"  ⬇ Downloading {repo['full_name']} archive...")
    headers = get_github_headers()
    owner, name = repo["owner"], repo["name"]

    zip_urls = [
        f"https://api.github.com/repos/{owner}/{name}/zipball",
        f"https://github.com/{owner}/{name}/archive/refs/heads/{repo['default_branch']}.zip",
        f"https://github.com/{owner}/{name}/archive/refs/heads/main.zip",
        f"https://github.com/{owner}/{name}/archive/refs/heads/master.zip",
    ]

    zip_data = None
    for url in zip_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 500:
                zip_data = resp.content
                break
        except requests.RequestException:
            continue

    if not zip_data:
        raise RuntimeError(f"Could not download ZIP archive for repository {repo['full_name']}")

    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            zf.extractall(target_dir)
        print(f"  ✓ Saved & extracted to: repo_cache/{safe_folder_name}")
        return target_dir
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"Downloaded ZIP archive for {repo['full_name']} was corrupted: {exc}")


# ============================================================
# STEP 3 — FILE INSPECTION & TEXT EXTRACTION
# ============================================================

def extract_repository_documents(repo_dir: str, topic: str) -> list[dict]:
    """
    Inspects extracted repository files and extracts textual content from
    Markdown, Text, RST, JSON, and CSV files.
    """
    documents = []
    ignored_dirs = {
        ".git", "node_modules", "dist", "build", "target", "venv", ".venv",
        "__pycache__", ".github", ".idea", ".vscode", "assets", "images", "img"
    }
    allowed_extensions = {".md", ".mdx", ".txt", ".rst", ".json", ".csv"}
    topic_terms = [t.lower() for t in re.findall(r"\w+", topic)]
    priority_terms = ["interview", "question", "algo", "ds", "coding", "technical", "solution", "readme"] + topic_terms

    for root, dirs, files in os.walk(repo_dir):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in allowed_extensions:
                continue

            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, repo_dir)

            try:
                content = ""
                if ext in {".md", ".mdx", ".txt", ".rst"}:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(15000)  # Max 15k chars per file
                elif ext == ".json":
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                        content = json.dumps(data, indent=2)[:15000]
                elif ext == ".csv":
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        reader = csv.reader(f)
                        rows = [", ".join(row) for i, row in enumerate(reader) if i < 100]
                        content = "\n".join(rows)[:15000]

                content = content.strip()
                if len(content) < 50:
                    continue

                # Priority score for file relevance
                file_lower = rel_path.lower()
                priority = sum(2 for p in priority_terms if p in file_lower)

                documents.append({
                    "rel_path": rel_path,
                    "content": content,
                    "priority": priority,
                })
            except Exception:
                continue

    # Sort documents by priority
    documents.sort(key=lambda d: d["priority"], reverse=True)
    return documents


# ============================================================
# STEP 4 — CHUNKING & EMBEDDINGS & FAISS
# ============================================================

def chunk_documents(documents: list[dict]) -> list[dict]:
    """Splits documents into overlapping chunks with source file metadata."""
    chunks = []
    for doc in documents:
        text = doc["content"]
        rel_path = doc["rel_path"]

        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunk_text = text[start:end].strip()

            if len(chunk_text) >= 60:
                chunks.append({
                    "text": chunk_text,
                    "rel_path": rel_path,
                })

            if end >= len(text):
                break
            start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def build_faiss_index(chunks: list[dict], model: SentenceTransformer):
    """Encodes chunks into L2-normalized vectors and constructs a FAISS IndexFlatIP index."""
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True).astype("float32")

    # Normalize L2 -> inner product yields cosine similarity
    faiss.normalize_L2(embeddings)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    return index


def retrieve_top_k(query: str, model: SentenceTransformer, index, chunks: list[dict], k: int = TOP_K) -> list[dict]:
    """Performs semantic search to retrieve TOP-K most relevant chunks."""
    query_vec = model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(query_vec)

    k = min(k, len(chunks))
    scores, indices = index.search(query_vec, k)

    results = []
    for idx, score in zip(indices[0], scores[0]):
        results.append({
            "chunk": chunks[idx],
            "score": float(score),
        })
    return results


# ============================================================
# STEP 5 — GEMINI PROMPTS (QUESTION GENERATION & EVALUATION)
# ============================================================

def call_gemini_with_retry(prompt: str, max_retries: int = 4, initial_delay: float = 2.0) -> str:
    """
    Calls Gemini API with clean config (disabling AFC warning)
    and automatic retries with exponential backoff for temporary 503 high demand spikes.
    """
    config = types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )
    delay = initial_delay

    for attempt in range(1, max_retries + 1):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
            if response and response.text:
                return response.text.strip()
            raise RuntimeError("Empty response received from Gemini API.")
        except Exception as exc:
            if attempt == max_retries:
                raise exc
            print(f"\n  ⚠️ Gemini API high demand / temporary notice (attempt {attempt}/{max_retries}).")
            print(f"     Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
            delay *= 1.5


def generate_interview_question(topic: str, retrieved_results: list[dict]) -> str:
    """Uses Gemini to generate 1 targeted interview question based ONLY on retrieved context."""
    context_str = ""
    for i, res in enumerate(retrieved_results, start=1):
        context_str += f"\n--- SOURCE BLOCK {i} (File: {res['chunk']['rel_path']}) ---\n"
        context_str += res["chunk"]["text"] + "\n"

    prompt = f"""You are a senior technical interviewer.

USER QUERY / TOPIC:
{topic}

RETRIEVED INTERVIEW MATERIAL:
{context_str}

REQUIREMENTS:
- Use ONLY the retrieved interview material above.
- Select or formulate ONE strong interview question appropriate for a college student / fresher.
- Directly related to the user query: "{topic}".
- Prefer an actual question from the source when available.
- If rephrasing is necessary, preserve the exact technical meaning.
- Do NOT reveal the answer.
- Do NOT invent unsupported facts.
- Return ONLY the interview question text without intro/outro notes.
"""

    return call_gemini_with_retry(prompt)


def evaluate_candidate_answer(topic: str, question: str, user_answer: str, retrieved_results: list[dict]) -> str:
    """Evaluates user answer strictly against retrieved reference material."""
    context_str = ""
    for i, res in enumerate(retrieved_results, start=1):
        context_str += f"\n--- SOURCE BLOCK {i} (File: {res['chunk']['rel_path']}) ---\n"
        context_str += res["chunk"]["text"] + "\n"

    prompt = f"""You are an expert AI technical interviewer evaluating a candidate's answer.

USER QUERY / TOPIC:
{topic}

INTERVIEW QUESTION:
{question}

CANDIDATE ANSWER:
{user_answer}

RETRIEVED REFERENCE CONTEXT:
{context_str}

Evaluate the candidate's answer strictly against the retrieved reference context above.

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

How to improve:
- [Point 1]
- [Point 2]

Ideal Answer:
[Write a concise, reference-grounded ideal answer based on the retrieved context]

EVALUATION RULES:
- Give full credit for equivalent concepts even if expressed in candidate's own words.
- Do not penalize minor phrasing differences.
- Do not invent facts outside the retrieved reference context.
"""

    return call_gemini_with_retry(prompt)


def display_evaluation_report(raw: str):
    """Renders candidate evaluation in a clean, human-reviewed CLI report."""
    score_match = re.search(r"Score:\s*(\d+(?:\.\d+)?)\s*/\s*10", raw, re.IGNORECASE)
    verdict_match = re.search(r"Verdict:\s*\n*([^\n]+)", raw, re.IGNORECASE)

    score_val = float(score_match.group(1)) if score_match else None
    verdict_str = verdict_match.group(1).strip() if verdict_match else "Evaluated"
    score_str = f"{score_val:.1f} / 10.0" if score_val is not None else "N/A"

    print("-" * 70)
    print("ASSESSMENT REPORT")
    print(f"Status : {verdict_str:<28} Score : {score_str}")
    print("-" * 70)

    def extract_bullets(section_text: str) -> list[str]:
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

    good_match = re.search(r"(?:What was good|Strengths)[:\s]*\n(.*?)(?=(?:What is missing|How to improve|Ideal Answer|\Z))", raw, re.DOTALL | re.IGNORECASE)
    missing_match = re.search(r"(?:What is missing or incorrect|Gaps|Weaknesses)[:\s]*\n(.*?)(?=(?:How to improve|Ideal Answer|\Z))", raw, re.DOTALL | re.IGNORECASE)
    improve_match = re.search(r"(?:How to improve|Improvement|Recommendations)[:\s]*\n(.*?)(?=(?:Ideal Answer|\Z))", raw, re.DOTALL | re.IGNORECASE)
    ideal_match = re.search(r"(?:Ideal Answer|Reference Answer)[:\s]*\n(.*)", raw, re.DOTALL | re.IGNORECASE)

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
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
        print(cleaned.strip())

    print("\n" + "-" * 70)


def main():
    print("-" * 70)
    print("  Interview Practice CLI (v1.2)")
    print("  Dynamic repository indexing & curriculum benchmark simulator.")
    print("  Type a topic or concept to begin (or 'exit' to quit).")
    print("-" * 70)

    print("Initializing embedding model...", end=" ", flush=True)
    t0 = time.time()
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    print(f"ready in {time.time()-t0:.1f}s.")

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

            print(f"-> Searching repositories for '{user_query}'...", end=" ", flush=True)
            candidates = search_github_repositories(user_query)
            if not candidates:
                print("failed.")
                print(f"   No repositories matched '{user_query}'. Try another query.")
                continue
            print(f"found {len(candidates)} candidates.")

            selected_repo = candidates[0]
            print(f"-> Selected: {selected_repo['full_name']} ({selected_repo['stars']} stars)")

            print("-> Indexing documentation chunks...", end=" ", flush=True)
            try:
                repo_dir = download_and_cache_repo(selected_repo)
                documents = extract_repository_documents(repo_dir, user_query)
                if not documents:
                    print("failed.")
                    print("   No usable documentation files found. Try another topic.")
                    continue

                chunks = chunk_documents(documents)
                index = build_faiss_index(chunks, embedding_model)
                retrieved = retrieve_top_k(user_query, embedding_model, index, chunks, k=TOP_K)
                print(f"ready ({len(chunks)} blocks indexed).")
            except Exception as exc:
                print(f"error: {exc}")
                continue

            print("-> Generating challenge question...", end=" ", flush=True)
            try:
                question = generate_interview_question(user_query, retrieved)
                print("done.")
            except Exception as exc:
                print(f"error: {exc}")
                continue

            print("\n" + "-" * 70)
            print(f"CHALLENGE: {user_query.title()}")
            print(f"Source   : {selected_repo['full_name']}")
            print("-" * 70)
            print(f"\n{question.strip()}\n")
            print("-" * 70)
            print("Your response (type your answer, then press Enter):")
            user_answer = input("\n> ").strip()

            if not user_answer:
                print("Skipped.\n")
                continue

            print("\nAnalyzing answer against reference criteria...", end=" ", flush=True)
            try:
                evaluation = evaluate_candidate_answer(user_query, question, user_answer, retrieved)
                print("done.\n")
            except Exception as exc:
                print(f"error: {exc}")
                continue

            display_evaluation_report(evaluation)

            print("Source Attribution:")
            print(f"  Repository : {selected_repo['full_name']} ({selected_repo['url']})")
            used_files = sorted({res['chunk']['rel_path'] for res in retrieved})
            print(f"  Files Used : {', '.join(used_files)}")
            print()

        except KeyboardInterrupt:
            print("\n\nSession terminated.")
            break
        except Exception as exc:
            print(f"\n[error] An unexpected error occurred: {exc}\n")


if __name__ == "__main__":
    main()
