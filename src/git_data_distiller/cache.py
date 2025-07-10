"""Caching system for GitHub API responses."""

import hashlib
import json
import logging
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of GitHub API responses."""

    def __init__(
        self,
        cache_dir: Union[str, Path],
        ttl_seconds: int = 3600,
        max_size_mb: int = 100,
        enabled: bool = True,
    ):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.max_size_mb = max_size_mb
        self.enabled = enabled

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Cache initialized: {self.cache_dir}")

    def _get_cache_key(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key from URL and parameters."""
        key_data = f"{url}_{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cache_file(self, cache_key: str) -> Path:
        """Get cache file path for a given key."""
        return self.cache_dir / f"{cache_key}.cache"

    def _get_metadata_file(self, cache_key: str) -> Path:
        """Get metadata file path for a given key."""
        return self.cache_dir / f"{cache_key}.meta"

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Get cached response if available and not expired."""
        if not self.enabled:
            return None

        try:
            cache_key = self._get_cache_key(url, params)
            cache_file = self._get_cache_file(cache_key)
            metadata_file = self._get_metadata_file(cache_key)

            if not cache_file.exists() or not metadata_file.exists():
                return None

            # Check if cache is expired
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            cache_time = metadata.get("timestamp", 0)
            if time.time() - cache_time > self.ttl_seconds:
                logger.debug(f"Cache expired for key: {cache_key}")
                self._remove_cache_entry(cache_key)
                return None

            # Load cached data
            with open(cache_file, "rb") as f:
                data = pickle.load(f)

            logger.debug(f"Cache hit for key: {cache_key}")
            return data

        except Exception as e:
            logger.warning(f"Error reading cache: {e}")
            return None

    def set(self, url: str, data: Any, params: Optional[Dict[str, Any]] = None) -> None:
        """Store data in cache."""
        if not self.enabled:
            return

        try:
            cache_key = self._get_cache_key(url, params)
            cache_file = self._get_cache_file(cache_key)
            metadata_file = self._get_metadata_file(cache_key)

            # Store data
            with open(cache_file, "wb") as f:
                pickle.dump(data, f)

            # Store metadata
            metadata = {
                "timestamp": time.time(),
                "url": url,
                "params": params or {},
                "size": cache_file.stat().st_size,
            }

            with open(metadata_file, "w") as f:
                json.dump(metadata, f)

            logger.debug(f"Cache stored for key: {cache_key}")

            # Check cache size and cleanup if needed
            self._cleanup_if_needed()

        except Exception as e:
            logger.warning(f"Error writing cache: {e}")

    def _remove_cache_entry(self, cache_key: str) -> None:
        """Remove a cache entry."""
        try:
            cache_file = self._get_cache_file(cache_key)
            metadata_file = self._get_metadata_file(cache_key)

            if cache_file.exists():
                cache_file.unlink()
            if metadata_file.exists():
                metadata_file.unlink()

        except Exception as e:
            logger.warning(f"Error removing cache entry: {e}")

    def clear(self) -> None:
        """Clear all cache entries."""
        if not self.enabled:
            return

        try:
            for file in self.cache_dir.glob("*.cache"):
                file.unlink()
            for file in self.cache_dir.glob("*.meta"):
                file.unlink()
            logger.info("Cache cleared")
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")

    def _cleanup_if_needed(self) -> None:
        """Cleanup cache if it exceeds size limit."""
        try:
            total_size = self._get_cache_size_mb()

            if total_size > self.max_size_mb:
                logger.info(
                    f"Cache size ({total_size:.1f}MB) exceeds limit "
                    f"({self.max_size_mb}MB), cleaning up..."
                )
                self._cleanup_old_entries()

        except Exception as e:
            logger.warning(f"Error during cache cleanup: {e}")

    def _get_cache_size_mb(self) -> float:
        """Get total cache size in MB."""
        total_size = 0
        for file in self.cache_dir.glob("*"):
            if file.is_file():
                total_size += file.stat().st_size
        return total_size / (1024 * 1024)

    def _cleanup_old_entries(self) -> None:
        """Remove oldest cache entries until under size limit."""
        metadata_files = list(self.cache_dir.glob("*.meta"))

        # Sort by modification time
        metadata_files.sort(key=lambda f: f.stat().st_mtime)

        for metadata_file in metadata_files:
            if self._get_cache_size_mb() <= self.max_size_mb:
                break

            # Extract cache key from metadata filename
            cache_key = metadata_file.stem
            self._remove_cache_entry(cache_key)
            logger.debug(f"Removed old cache entry: {cache_key}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.enabled:
            return {"enabled": False}

        try:
            cache_files = list(self.cache_dir.glob("*.cache"))
            metadata_files = list(self.cache_dir.glob("*.meta"))

            total_size_mb = self._get_cache_size_mb()

            # Count expired entries
            expired_count = 0
            current_time = time.time()

            for metadata_file in metadata_files:
                try:
                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)

                    cache_time = metadata.get("timestamp", 0)
                    if current_time - cache_time > self.ttl_seconds:
                        expired_count += 1
                except Exception:
                    expired_count += 1

            return {
                "enabled": True,
                "entries": len(cache_files),
                "expired_entries": expired_count,
                "total_size_mb": round(total_size_mb, 2),
                "max_size_mb": self.max_size_mb,
                "ttl_seconds": self.ttl_seconds,
                "cache_dir": str(self.cache_dir),
            }

        except Exception as e:
            logger.warning(f"Error getting cache stats: {e}")
            return {"enabled": True, "error": str(e)}


class CachedGitHubClient:
    """GitHub client wrapper with caching."""

    def __init__(self, client, cache_manager: CacheManager):
        self.client = client
        self.cache = cache_manager

    def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get data with caching."""
        # Check cache first
        cached_data = self.cache.get(endpoint, params)
        if cached_data is not None:
            return cached_data

        # Fetch from API
        data = self.client.get(endpoint, params)

        # Cache the result
        self.cache.set(endpoint, data, params)

        return data

    def get_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        per_page: int = 100,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get paginated data with caching."""
        # For paginated requests, we cache each page separately
        all_items = []
        page = 1

        if params is None:
            params = {}

        base_params = params.copy()
        base_params["per_page"] = per_page

        while True:
            if max_pages and page > max_pages:
                break

            page_params = base_params.copy()
            page_params["page"] = page

            # Create cache key for this specific page
            page_endpoint = f"{endpoint}_page_{page}"

            # Check cache first
            cached_data = self.cache.get(page_endpoint, page_params)
            if cached_data is not None:
                data = cached_data
            else:
                # Fetch from API
                data = self.client.get(endpoint, page_params)
                # Cache the result
                self.cache.set(page_endpoint, data, page_params)

            if not data:
                break

            if isinstance(data, list):
                all_items.extend(data)
                if len(data) < per_page:
                    break
            else:
                # Handle search results format
                if "items" in data:
                    all_items.extend(data["items"])
                    if len(data["items"]) < per_page:
                        break
                else:
                    all_items.append(data)
                    break

            page += 1

        return all_items

    def __getattr__(self, name):
        """Delegate other attributes to the underlying client."""
        return getattr(self.client, name)
