"""
=============================================================================
                    LRU & TTL CACHE MANAGER
=============================================================================
Manages physical repository disk cache (repo_cache/) and dynamic vector topic
metadata (dynamic_cache.json) using bounded capacity (LRU) and time expiration (TTL).
=============================================================================
"""

import os
import time
import json
import shutil
from typing import List, Dict, Any, Optional, Tuple

DEFAULT_REPO_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "repo_cache"
)


class CacheManager:
    """
    Unified LRU and TTL Cache Manager for:
    1. Disk storage: repo_cache/ (Bounded by count, disk size in MB, and TTL days).
    2. Metadata storage: dynamic_cache.json (Bounded by topic count and TTL days).
    """

    def __init__(
        self,
        cache_dir: str = DEFAULT_REPO_CACHE_DIR,
        max_repos: int = 15,
        max_disk_mb: float = 300.0,
        repo_ttl_days: int = 30,
        max_dynamic_topics: int = 50,
        topic_ttl_days: int = 14,
    ):
        self.cache_dir = cache_dir
        self.max_repos = max_repos
        self.max_disk_bytes = int(max_disk_mb * 1024 * 1024)
        self.repo_ttl_seconds = repo_ttl_days * 86400
        self.max_dynamic_topics = max_dynamic_topics
        self.topic_ttl_seconds = topic_ttl_days * 86400

        os.makedirs(self.cache_dir, exist_ok=True)
        self.metadata_file = os.path.join(self.cache_dir, "cache_metadata.json")
        self._sync_disk_metadata()

    # -------------------------------------------------------------------------
    # 1. DISK CACHE (repo_cache/) MANAGEMENT (LRU + TTL)
    # -------------------------------------------------------------------------

    def _load_disk_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Loads disk cache metadata registry."""
        if not os.path.exists(self.metadata_file):
            return {}
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_disk_metadata(self, meta: Dict[str, Dict[str, Any]]):
        """Saves disk cache metadata registry."""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            print(f"  [WARN] Failed to write cache metadata: {e}")

    def _get_dir_size(self, path: str) -> int:
        """Calculates total size of a directory in bytes."""
        total = 0
        try:
            for root, _, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    if not os.path.islink(fp) and os.path.exists(fp):
                        total += os.path.getsize(fp)
        except Exception:
            pass
        return total

    def _sync_disk_metadata(self):
        """Synchronizes metadata file with actual folders present on disk."""
        meta = self._load_disk_metadata()
        existing_folders = set()

        if os.path.exists(self.cache_dir):
            for item in os.listdir(self.cache_dir):
                item_path = os.path.join(self.cache_dir, item)
                if os.path.isdir(item_path):
                    existing_folders.add(item)
                    if item not in meta:
                        size = self._get_dir_size(item_path)
                        mtime = os.path.getmtime(item_path)
                        meta[item] = {
                            "folder_name": item,
                            "folder_path": item_path,
                            "size_bytes": size,
                            "created_at": mtime,
                            "last_accessed_at": mtime,
                        }

        # Remove metadata for folders that no longer exist
        for item in list(meta.keys()):
            if item not in existing_folders:
                del meta[item]

        self._save_disk_metadata(meta)

    def record_repo_access(self, folder_name: str, folder_path: Optional[str] = None):
        """Records an access hit for a cached repository, updating its LRU timestamp."""
        meta = self._load_disk_metadata()
        now = time.time()
        path = folder_path or os.path.join(self.cache_dir, folder_name)

        if folder_name in meta:
            meta[folder_name]["last_accessed_at"] = now
            if not meta[folder_name].get("size_bytes"):
                meta[folder_name]["size_bytes"] = self._get_dir_size(path)
        else:
            meta[folder_name] = {
                "folder_name": folder_name,
                "folder_path": path,
                "size_bytes": self._get_dir_size(path),
                "created_at": now,
                "last_accessed_at": now,
            }

        self._save_disk_metadata(meta)

    def prune_repo_cache(self) -> List[str]:
        """
        Executes LRU and TTL eviction on repo_cache/:
        1. TTL Pass: Evicts repositories older than repo_ttl_days.
        2. LRU Pass: If total repos > max_repos OR total bytes > max_disk_bytes,
           evicts least recently accessed repositories until bounds are met.
        Returns list of pruned folder names.
        """
        self._sync_disk_metadata()
        meta = self._load_disk_metadata()
        now = time.time()
        pruned = []

        # 1. TTL Pass (Expiration)
        for folder_name, info in list(meta.items()):
            created_at = info.get("created_at", now)
            if (now - created_at) > self.repo_ttl_seconds:
                folder_path = info.get("folder_path") or os.path.join(self.cache_dir, folder_name)
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path, ignore_errors=True)
                del meta[folder_name]
                pruned.append(f"{folder_name} (TTL expired)")

        # 2. LRU Pass (Capacity & Byte Size Bounds)
        def get_total_size(items: Dict[str, Dict[str, Any]]) -> int:
            return sum(it.get("size_bytes", 0) for it in items.values())

        # Sort remaining repositories by last_accessed_at ascending (oldest access first)
        sorted_repos = sorted(meta.items(), key=lambda x: x[1].get("last_accessed_at", 0))

        while sorted_repos and (
            len(sorted_repos) > self.max_repos
            or get_total_size(meta) > self.max_disk_bytes
        ):
            oldest_name, oldest_info = sorted_repos.pop(0)
            folder_path = oldest_info.get("folder_path") or os.path.join(self.cache_dir, oldest_name)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path, ignore_errors=True)
            if oldest_name in meta:
                del meta[oldest_name]
            pruned.append(f"{oldest_name} (LRU evicted)")

        self._save_disk_metadata(meta)

        if pruned:
            for p in pruned:
                print(f"  [CACHE PRUNE] Evicted repository: {p}")

        return pruned

    # -------------------------------------------------------------------------
    # 2. DYNAMIC TOPICS METADATA (dynamic_cache.json) MANAGEMENT (LRU + TTL)
    # -------------------------------------------------------------------------

    def prune_dynamic_topics(self, cached_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Prunes dynamic topics from dynamic_cache.json using TTL and LRU policies.
        1. TTL: Removes topics where (now - created_at) > topic_ttl_seconds.
        2. LRU: Keeps up to max_dynamic_topics sorted by last_accessed_at descending.
        Returns: (pruned_items_list, list_of_evicted_topic_names)
        """
        if not cached_items:
            return [], []

        now = time.time()
        valid_items = []
        evicted = []

        # 1. TTL Pass
        for item in cached_items:
            created_at = item.get("created_at", now)
            # Ensure timestamps exist
            if "created_at" not in item:
                item["created_at"] = now
            if "last_accessed_at" not in item:
                item["last_accessed_at"] = now

            if (now - created_at) > self.topic_ttl_seconds:
                evicted.append(f"{item.get('topic', 'Unknown')} (TTL expired)")
            else:
                valid_items.append(item)

        # 2. LRU Pass
        if len(valid_items) > self.max_dynamic_topics:
            # Sort by last_accessed_at descending (most recent first)
            valid_items.sort(key=lambda x: x.get("last_accessed_at", 0), reverse=True)
            excess = valid_items[self.max_dynamic_topics :]
            valid_items = valid_items[: self.max_dynamic_topics]
            for itm in excess:
                evicted.append(f"{itm.get('topic', 'Unknown')} (LRU evicted)")

        if evicted:
            for e in evicted:
                print(f"  [CACHE PRUNE] Evicted topic: {e}")

        return valid_items, evicted
