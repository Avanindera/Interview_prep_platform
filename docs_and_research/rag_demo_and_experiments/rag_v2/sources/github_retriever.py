"""
=============================================================================
                    GITHUB REPOSITORY RETRIEVER
=============================================================================
Discovers the highest-quality GitHub interview / coding repository matching
a topic, downloads/caches it locally, and extracts & chunks technical text.
=============================================================================
"""

import os
import io
import re
import json
import csv
import zipfile
import math
from urllib.parse import quote
from typing import List, Dict, Any, Optional
import requests

from rag_v2.sources.cache_manager import CacheManager

DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "repo_cache")


class GitHubRetriever:
    def __init__(self, token: Optional[str] = None, cache_dir: str = DEFAULT_CACHE_DIR, cache_manager: Optional[CacheManager] = None):
        self.token = token or os.getenv("GITHUB_TOKEN", "").strip()
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_manager = cache_manager or CacheManager(cache_dir=self.cache_dir)

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Interview-RAG-v2",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def search_best_repository(self, topic: str) -> Optional[Dict[str, Any]]:
        """Searches GitHub API for repositories and ranks them by topic relevance & stars."""
        topic_clean = topic.strip()
        queries = [
            f"{topic_clean} interview questions",
            f"{topic_clean} coding interview",
            f"{topic_clean} technical interview",
            f"data structures algorithms {topic_clean}",
        ]
        headers = self._get_headers()
        candidates = {}

        for q in queries[:2]:
            url = f"https://api.github.com/search/repositories?q={quote(q)}&sort=stars&order=desc&per_page=8"
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code in (403, 429):
                    print("  [warn] GitHub API rate limit reached.")
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
            except Exception as e:
                print(f"  ⚠️ Error searching GitHub for '{q}': {e}")
                continue

        if not candidates:
            return None

        # Rank candidates
        topic_words = set(re.findall(r"\w+", topic.lower()))
        interview_keywords = {"interview", "questions", "answers", "prep", "coding", "technical", "algo", "ds", "awesome", "guide"}

        ranked = []
        for repo in candidates.values():
            desc_lower = (repo["name"] + " " + repo["description"]).lower()
            desc_words = set(re.findall(r"\w+", desc_lower))

            topic_matches = len(topic_words.intersection(desc_words))
            interview_matches = len(interview_keywords.intersection(desc_words))
            star_score = math.log10(repo["stars"] + 1) * 2
            relevance_score = (topic_matches * 3.5) + (interview_matches * 2.0) + star_score

            repo_copy = dict(repo)
            repo_copy["relevance_score"] = round(relevance_score, 2)
            ranked.append(repo_copy)

        ranked.sort(key=lambda x: x["relevance_score"], reverse=True)
        return ranked[0] if ranked else None

    def download_and_extract_repo(self, repo: Dict[str, Any]) -> str:
        """Downloads repository ZIP archive and extracts it to cache_dir."""
        safe_name = repo["full_name"].replace("/", "_")
        target_dir = os.path.join(self.cache_dir, safe_name)

        if os.path.exists(target_dir) and os.listdir(target_dir):
            print(f"  [CACHE] Using locally cached GitHub repository: repo_cache/{safe_name}")
            self.cache_manager.record_repo_access(safe_name, target_dir)
            return target_dir

        # Prune older repositories before new download
        self.cache_manager.prune_repo_cache()

        print(f"  [DOWNLOAD] Downloading GitHub repository: {repo['full_name']}...")
        headers = self._get_headers()
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
                resp = requests.get(url, headers=headers, timeout=25, allow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 500:
                    zip_data = resp.content
                    break
            except Exception:
                continue

        if not zip_data:
            raise RuntimeError(f"Failed to download repository ZIP for {repo['full_name']}")

        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            zf.extractall(target_dir)

        self.cache_manager.record_repo_access(safe_name, target_dir)
        self.cache_manager.prune_repo_cache()

        print(f"  [OK] Downloaded & extracted GitHub repo to: repo_cache/{safe_name}")
        return target_dir

    def extract_and_chunk_repo(self, repo_dir: str, repo_info: Dict[str, Any], topic: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, Any]]:
        """Extracts text from files in repo directory and creates chunks with metadata."""
        chunks = []
        allowed_exts = {".md", ".mdx", ".txt", ".rst", ".json"}
        ignored_dirs = {".git", "node_modules", "dist", "build", "target", "venv", ".venv", "__pycache__", "assets", "img", "images"}

        topic_terms = [t.lower() for t in re.findall(r"\w+", topic)]
        priority_terms = ["interview", "question", "algo", "ds", "coding", "technical", "solution", "readme"] + topic_terms

        raw_docs = []
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in allowed_exts:
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_dir)

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read(15000).strip()
                    if len(text) < 60:
                        continue

                    # Priority score
                    rel_lower = rel_path.lower()
                    p_score = sum(2 for p in priority_terms if p in rel_lower)
                    raw_docs.append({"rel_path": rel_path, "content": text, "priority": p_score})
                except Exception:
                    continue

        # Sort highest priority files first
        raw_docs.sort(key=lambda d: d["priority"], reverse=True)

        for doc in raw_docs[:10]:  # Inspect top 10 relevant files
            text = doc["content"]
            rel_path = doc["rel_path"]
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunk_text = text[start:end].strip()
                if len(chunk_text) >= 60:
                    chunks.append({
                        "source": f"GitHub: {repo_info['full_name']} ({rel_path})",
                        "source_type": "github",
                        "repo_name": repo_info["full_name"],
                        "repo_url": repo_info["url"],
                        "file": rel_path,
                        "text": chunk_text,
                    })
                if end >= len(text):
                    break
                start += chunk_size - chunk_overlap

        return chunks
