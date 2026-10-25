"""
=============================================================================
                    OFFLINE CACHE & VECTOR DATABASE STORE
=============================================================================
This module manages the offline knowledge base and FAISS vector index.
It performs semantic similarity matching against local cached interview topics.
If the best cosine similarity score >= SIMILARITY_THRESHOLD (default 0.70),
it retrieves offline context instantly without making online network calls.
=============================================================================
"""

import os
import json
import faiss
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from sentence_transformers import SentenceTransformer

from app.rag.sources.cache_manager import CacheManager

DEFAULT_OFFLINE_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "offline_db")
DEFAULT_THRESHOLD = 0.52  # Cosine similarity threshold for offline hit


class OfflineKnowledgeStore:
    def __init__(
        self,
        db_dir: str = DEFAULT_OFFLINE_DB_DIR,
        model: Optional[SentenceTransformer] = None,
        threshold: float = DEFAULT_THRESHOLD,
        cache_manager: Optional[CacheManager] = None,
    ):
        self.db_dir = db_dir
        self.threshold = threshold
        self.model = model
        self.cache_manager = cache_manager or CacheManager()
        self.chunks: List[Dict[str, Any]] = []
        self.topics_data: List[Dict[str, Any]] = []
        self.index: Optional[faiss.IndexFlatIP] = None
        self.dimension: int = 384

        os.makedirs(self.db_dir, exist_ok=True)
        self.load_database()

    def set_model(self, model: SentenceTransformer):
        """Sets or updates the embedding model and builds the FAISS index."""
        self.model = model
        self._rebuild_index()

    def load_database(self):
        """Loads all JSON files from the offline database directory."""
        self.chunks = []
        self.topics_data = []

        if not os.path.exists(self.db_dir):
            return

        for filename in sorted(os.listdir(self.db_dir)):
            if filename.endswith(".json"):
                filepath = os.path.join(self.db_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                        # Apply LRU and TTL pruning to dynamic cache
                        if filename == "dynamic_cache.json" and isinstance(data, list):
                            pruned_data, evicted = self.cache_manager.prune_dynamic_topics(data)
                            if evicted:
                                with open(filepath, "w", encoding="utf-8") as fw:
                                    json.dump(pruned_data, fw, indent=2)
                            data = pruned_data

                        if isinstance(data, list):
                            for item in data:
                                self._ingest_topic_item(item, source_file=filename)
                        elif isinstance(data, dict):
                            self._ingest_topic_item(data, source_file=filename)
                except Exception as e:
                    print(f"  [warn] Failed to parse offline DB file {filename}: {e}")

        if self.model and self.chunks:
            self._rebuild_index()

    def _ingest_topic_item(self, item: Dict[str, Any], source_file: str):
        """Ingests a structured topic item into chunks and indexed metadata."""
        self.topics_data.append(item)
        topic_title = item.get("topic", "Untitled Topic")
        category = item.get("category", "General")
        summary = item.get("summary", "")
        aliases = item.get("aliases", [])
        key_concepts = item.get("key_concepts", [])
        common_misconceptions = item.get("common_misconceptions", [])
        interview_questions = item.get("interview_questions", [])

        # 1. Summary & Topic header chunk
        header_text = f"Topic: {topic_title}\nCategory: {category}\nAliases: {', '.join(aliases)}\nSummary: {summary}"
        self.chunks.append({
            "topic": topic_title,
            "text": header_text,
            "source": f"offline_db/{source_file}",
            "type": "summary",
            "metadata": item,
        })

        # 2. Key concepts chunk
        if key_concepts:
            concepts_text = f"Topic: {topic_title} - Key Technical Concepts:\n" + "\n".join(f"- {c}" for c in key_concepts)
            self.chunks.append({
                "topic": topic_title,
                "text": concepts_text,
                "source": f"offline_db/{source_file}",
                "type": "concepts",
                "metadata": item,
            })

        # 3. Misconceptions chunk
        if common_misconceptions:
            misconception_text = f"Topic: {topic_title} - Common Interview Misconceptions & Pitfalls:\n" + "\n".join(f"- {m}" for m in common_misconceptions)
            self.chunks.append({
                "topic": topic_title,
                "text": misconception_text,
                "source": f"offline_db/{source_file}",
                "type": "misconceptions",
                "metadata": item,
            })

        # 4. Questions chunks
        for q_idx, q in enumerate(interview_questions):
            q_text = q.get("question", "")
            ans_text = q.get("ideal_answer", "")
            full_q_text = f"Topic: {topic_title} - Question #{q_idx+1}:\nQ: {q_text}\nIdeal Answer: {ans_text}"
            self.chunks.append({
                "topic": topic_title,
                "text": full_q_text,
                "source": f"offline_db/{source_file}",
                "type": "qa_pair",
                "question": q_text,
                "ideal_answer": ans_text,
                "metadata": item,
            })

    def _rebuild_index(self):
        """Encodes all text chunks with sentence-transformers and builds FAISS index."""
        if not self.model or not self.chunks:
            self.index = None
            return

        texts = [c["text"] for c in self.chunks]
        embeddings = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(embeddings)
        self.dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(embeddings)

    def search_offline(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Searches offline database using FAISS semantic search.
        Returns:
            dict containing:
              - matched (bool): True if best similarity >= threshold
              - best_score (float): Highest cosine similarity score
              - threshold (float): Active similarity threshold
              - best_topic (str): Closest matched topic
              - results (list[dict]): Retrieved chunks with similarity scores
        """
        if not self.index or not self.model or not self.chunks:
            return {
                "matched": False,
                "best_score": 0.0,
                "threshold": self.threshold,
                "best_topic": None,
                "results": [],
            }

        query_vec = self.model.encode([query], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(query_vec)

        k = min(top_k, len(self.chunks))
        scores, indices = self.index.search(query_vec, k)

        matched_results = []
        best_score = 0.0
        best_topic = None

        for idx, score in zip(indices[0], scores[0]):
            chunk_data = self.chunks[idx]
            s = float(score)
            if s > best_score:
                best_score = s
                best_topic = chunk_data.get("topic")

            matched_results.append({
                "chunk": chunk_data,
                "score": round(s, 4),
            })

        is_matched = best_score >= self.threshold

        if is_matched and best_topic:
            self._touch_dynamic_topic(best_topic)

        return {
            "matched": is_matched,
            "best_score": round(best_score, 4),
            "threshold": self.threshold,
            "best_topic": best_topic,
            "results": matched_results,
        }

    def _touch_dynamic_topic(self, topic: str):
        """Updates last_accessed_at timestamp for a dynamic cache topic on access hit."""
        dynamic_file = os.path.join(self.db_dir, "dynamic_cache.json")
        if not os.path.exists(dynamic_file):
            return
        try:
            with open(dynamic_file, "r", encoding="utf-8") as f:
                cached_items = json.load(f)
            if not isinstance(cached_items, list):
                return
            updated = False
            now = time.time()
            for itm in cached_items:
                if itm.get("topic", "").lower() == topic.lower():
                    itm["last_accessed_at"] = now
                    updated = True
                    break
            if updated:
                with open(dynamic_file, "w", encoding="utf-8") as f:
                    json.dump(cached_items, f, indent=2)
        except Exception:
            pass

    def save_dynamic_cache(self, topic: str, chunks: List[Dict[str, Any]], generated_qa: Optional[Dict[str, str]] = None):
        """
        Saves online retrieved & synthesized interview knowledge into local offline database
        so subsequent runs can hit offline cache immediately, applying LRU and TTL limits.
        """
        dynamic_file = os.path.join(self.db_dir, "dynamic_cache.json")
        cached_items = []
        if os.path.exists(dynamic_file):
            try:
                with open(dynamic_file, "r", encoding="utf-8") as f:
                    cached_items = json.load(f)
                    if not isinstance(cached_items, list):
                        cached_items = []
            except Exception:
                cached_items = []

        # Build topic item
        questions = []
        if generated_qa:
            questions.append({
                "question": generated_qa.get("question", ""),
                "ideal_answer": generated_qa.get("ideal_answer", "")
            })

        summary_snippets = [c["text"][:300] for c in chunks[:3]]
        now = time.time()

        new_entry = {
            "topic": topic,
            "category": "Dynamically Cached Online Topic",
            "aliases": [topic.lower()],
            "summary": " \n".join(summary_snippets),
            "key_concepts": [c["text"][:250] for c in chunks[:4]],
            "interview_questions": questions,
            "common_misconceptions": [],
            "created_at": now,
            "last_accessed_at": now,
        }

        # Check if already exists in cached_items
        existing_idx = None
        for i, itm in enumerate(cached_items):
            if itm.get("topic", "").lower() == topic.lower():
                existing_idx = i
                break

        if existing_idx is not None:
            new_entry["created_at"] = cached_items[existing_idx].get("created_at", now)
            cached_items[existing_idx] = new_entry
        else:
            cached_items.append(new_entry)

        # Apply LRU + TTL pruning
        cached_items, _ = self.cache_manager.prune_dynamic_topics(cached_items)

        try:
            with open(dynamic_file, "w", encoding="utf-8") as f:
                json.dump(cached_items, f, indent=2)
            # Ingest and rebuild
            self._ingest_topic_item(new_entry, source_file="dynamic_cache.json")
            self._rebuild_index()
            print(f"  [OK] Saved '{topic}' to local offline cache database (dynamic_cache.json).")
        except Exception as e:
            print(f"  [WARN] Error saving to dynamic offline cache: {e}")
