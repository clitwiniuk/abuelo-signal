"""
Worker State Cache - Persistent state management for workers

Solves the problem of workers losing state between scanner cycles.
Provides a singleton cache that persists across worker evaluations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import threading


@dataclass
class CachedState:
    """Cached state entry with TTL"""
    data: Any
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    ttl_hours: float = 4.0  # Default 4 hours for intraday

    def is_expired(self) -> bool:
        """Check if this state has expired"""
        age = datetime.now() - self.created_at
        return age > timedelta(hours=self.ttl_hours)

    def update(self, data: Any):
        """Update data and refresh timestamp"""
        self.data = data
        self.last_updated = datetime.now()


class WorkerStateCache:
    """
    Singleton cache for worker state persistence

    Features:
    - Thread-safe access
    - Automatic expiration (TTL)
    - Worker-namespaced storage
    - Periodic cleanup

    Usage:
        cache = WorkerStateCache()
        cache.set('livermore', 'AAPL', candidate_data, ttl_hours=6.0)
        data = cache.get('livermore', 'AAPL')
    """

    _instance: Optional['WorkerStateCache'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._cache: Dict[str, Dict[str, CachedState]] = {}
        self._cache_lock = threading.RLock()
        self._logger = logging.getLogger("WorkerStateCache")
        self._initialized = True
        self._last_cleanup = datetime.now()

        self._logger.info("🗄️ WorkerStateCache initialized (Singleton)")

    def set(self, worker_name: str, key: str, data: Any, ttl_hours: float = 4.0):
        """
        Store data in cache with TTL

        Args:
            worker_name: Namespace for the worker (e.g., 'livermore')
            key: Key within worker namespace (e.g., symbol 'AAPL')
            data: Data to cache (e.g., LivermoreCandidate object)
            ttl_hours: Time to live in hours (default 4h for intraday)
        """
        with self._cache_lock:
            if worker_name not in self._cache:
                self._cache[worker_name] = {}

            if key in self._cache[worker_name]:
                # Update existing entry
                self._cache[worker_name][key].update(data)
            else:
                # Create new entry
                self._cache[worker_name][key] = CachedState(
                    data=data,
                    ttl_hours=ttl_hours
                )

            # Periodic cleanup (every 5 minutes)
            if (datetime.now() - self._last_cleanup).total_seconds() > 300:
                self._cleanup_expired()

    def get(self, worker_name: str, key: str) -> Optional[Any]:
        """
        Retrieve data from cache

        Args:
            worker_name: Namespace for the worker
            key: Key within worker namespace

        Returns:
            Cached data or None if not found/expired
        """
        with self._cache_lock:
            if worker_name not in self._cache:
                return None

            if key not in self._cache[worker_name]:
                return None

            cached = self._cache[worker_name][key]

            if cached.is_expired():
                # Remove expired entry
                del self._cache[worker_name][key]
                return None

            return cached.data

    def get_all(self, worker_name: str) -> Dict[str, Any]:
        """
        Get all cached entries for a worker

        Args:
            worker_name: Namespace for the worker

        Returns:
            Dict of {key: data} for all non-expired entries
        """
        with self._cache_lock:
            if worker_name not in self._cache:
                return {}

            result = {}
            expired_keys = []

            for key, cached in self._cache[worker_name].items():
                if cached.is_expired():
                    expired_keys.append(key)
                else:
                    result[key] = cached.data

            # Clean up expired entries
            for key in expired_keys:
                del self._cache[worker_name][key]

            return result

    def delete(self, worker_name: str, key: str):
        """Remove entry from cache"""
        with self._cache_lock:
            if worker_name in self._cache and key in self._cache[worker_name]:
                del self._cache[worker_name][key]

    def clear_worker(self, worker_name: str):
        """Clear all entries for a worker"""
        with self._cache_lock:
            if worker_name in self._cache:
                del self._cache[worker_name]
                self._logger.info(f"🗑️ Cleared cache for worker: {worker_name}")

    def _cleanup_expired(self):
        """Internal cleanup of expired entries"""
        with self._cache_lock:
            total_removed = 0

            for worker_name in list(self._cache.keys()):
                expired_keys = [
                    key for key, cached in self._cache[worker_name].items()
                    if cached.is_expired()
                ]

                for key in expired_keys:
                    del self._cache[worker_name][key]
                    total_removed += 1

                # Remove empty worker namespaces
                if not self._cache[worker_name]:
                    del self._cache[worker_name]

            if total_removed > 0:
                self._logger.info(f"🗑️ Cleaned up {total_removed} expired cache entries")

            self._last_cleanup = datetime.now()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._cache_lock:
            stats = {}
            total_entries = 0

            for worker_name, entries in self._cache.items():
                active = sum(1 for c in entries.values() if not c.is_expired())
                expired = sum(1 for c in entries.values() if c.is_expired())
                stats[worker_name] = {
                    'active': active,
                    'expired': expired,
                    'total': len(entries)
                }
                total_entries += active

            stats['_total'] = total_entries
            stats['_workers'] = len(self._cache)

            return stats


# Global convenience function
def get_worker_cache() -> WorkerStateCache:
    """Get the singleton WorkerStateCache instance"""
    return WorkerStateCache()
