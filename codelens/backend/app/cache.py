"""
cache.py – Unified caching layer for CodeLens.

Tries Redis first; falls back to an in-memory LRU cache if Redis is
unavailable or misconfigured.

Cache keys:
  - query results:    "q:{sha256(query+version+config_hash)}"
  - query embeddings: "emb:{sha256(query)}"
"""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
from typing import Any, Optional

from cachetools import LRUCache

logger = logging.getLogger("codelens.cache")

# ──────────────────────────── Redis (optional) ─────────────────────────────

try:
    import redis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    logger.info("redis-py not installed; using in-memory LRU cache only.")


class CacheBackend:
    """
    Unified cache that tries Redis and falls back to LRU.

    Parameters
    ----------
    redis_url:    Redis connection string (e.g. "redis://localhost:6379")
    ttl:          TTL in seconds for Redis entries (in-memory has no TTL)
    max_size:     Maximum entries for the in-memory LRU fallback
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl: int = 3600,
        max_size: int = 1024,
    ) -> None:
        self.ttl = ttl
        self._redis: Optional["redis.Redis"] = None
        self._lru: LRUCache = LRUCache(maxsize=max_size)
        self._using_redis = False

        if _REDIS_AVAILABLE:
            try:
                client = redis.from_url(redis_url, socket_connect_timeout=1)
                client.ping()
                self._redis = client
                self._using_redis = True
                logger.info("Redis cache connected: %s", redis_url)
            except Exception as exc:
                logger.info("Redis unavailable (%s); using in-memory LRU cache", exc)

    @property
    def backend_name(self) -> str:
        return "redis" if self._using_redis else "lru"

    # ──────────────────────────── Public API ──────────────────────

    def get(self, key: str) -> Optional[Any]:
        if self._using_redis and self._redis:
            try:
                val = self._redis.get(key)
                if val is not None:
                    return pickle.loads(val)
            except Exception as exc:
                logger.debug("Redis GET error: %s", exc)
        return self._lru.get(key)

    def set(self, key: str, value: Any) -> None:
        if self._using_redis and self._redis:
            try:
                self._redis.setex(key, self.ttl, pickle.dumps(value))
                return
            except Exception as exc:
                logger.debug("Redis SET error: %s", exc)
        self._lru[key] = value

    def delete(self, key: str) -> None:
        if self._using_redis and self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._lru.pop(key, None)

    def flush(self) -> None:
        if self._using_redis and self._redis:
            try:
                self._redis.flushdb()
            except Exception:
                pass
        self._lru.clear()

    def stats(self) -> dict:
        info: dict = {"backend": self.backend_name}
        if self._using_redis and self._redis:
            try:
                r_info = self._redis.info("stats")
                info["redis_hits"] = r_info.get("keyspace_hits", 0)
                info["redis_misses"] = r_info.get("keyspace_misses", 0)
            except Exception:
                pass
        info["lru_size"] = len(self._lru)
        info["lru_max_size"] = self._lru.maxsize
        return info


# ──────────────────────────── Key helpers ──────────────────────────────────

def make_query_cache_key(query: str, version: str, config_hash: str) -> str:
    raw = f"{query}::{version}::{config_hash}"
    return "q:" + hashlib.sha256(raw.encode()).hexdigest()


def make_embed_cache_key(query: str) -> str:
    return "emb:" + hashlib.sha256(query.encode()).hexdigest()


def config_hash(cfg: dict) -> str:
    """Stable hash of a config dict for cache keying."""
    canon = json.dumps(cfg, sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


# ──────────────────────────── Singleton ───────────────────────────────────

_cache: Optional[CacheBackend] = None


def get_cache(
    redis_url: str = "redis://localhost:6379",
    ttl: int = 3600,
    max_size: int = 1024,
) -> CacheBackend:
    global _cache
    if _cache is None:
        _cache = CacheBackend(redis_url=redis_url, ttl=ttl, max_size=max_size)
    return _cache
