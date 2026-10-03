"""
CodeLens configuration module.
All tuneable knobs live here. Override via environment variables or a
.env file (loaded by python-dotenv in main.py).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ──────────────────────────── Paths ────────────────────────────
    # base_dir is the backend/ directory (parent of backend/app/)
    base_dir: Path = Path(__file__).parent.parent
    # Allow override via INDEXES_DIR env var (e.g. Render persistent disk: /var/data/indexes)
    indexes_dir: Path = Path(os.environ.get("INDEXES_DIR", "") or (Path(__file__).parent.parent / "indexes"))
    results_dir: Path = base_dir / "results"

    # ──────────────────────────── Models ───────────────────────────
    # all-MiniLM-L6-v2 is ~80 MB — fits comfortably in Render's 512 MB free-tier RAM.
    # bge-small-en-v1.5 is ~134 MB and causes OOM crashes on free-tier Render.
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Fallback when primary is unavailable / too slow
    embed_model_fallback: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Cross-encoder reranker
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Embedding dimension — must match the model (all-MiniLM-L6-v2 = 384)
    embed_dim: int = 384

    # ──────────────────────────── Retrieval pipeline toggles ───────
    use_bm25: bool = True         # enable BM25 sparse retrieval
    use_hybrid: bool = True       # fuse BM25 + dense with RRF
    use_rerank: bool = False      # cross-encoder reranker (disabled by default on 512MB RAM free-tier)
    use_query_clean: bool = True  # query normalization / cleaning
    use_doc_normalize: bool = True  # document normalization
    use_second_pass: bool = False  # keyword expansion second pass
    use_version_collapse: bool = True  # group by lineage_id

    # ──────────────────────────── BM25 ─────────────────────────────
    bm25_top_k: int = 100
    dense_top_k: int = 100
    rrf_k: int = 60               # RRF constant (standard = 60)
    rerank_top_k: int = 30        # how many to send to reranker
    final_top_k: int = 10         # results returned to caller

    # ──────────────────────────── FAISS ────────────────────────────
    faiss_index_type: Literal["flat", "hnsw"] = "flat"
    hnsw_m: int = 32
    hnsw_ef_construction: int = 200
    hnsw_ef_search: int = 50

    # ──────────────────────────── Chunking ─────────────────────────
    max_chunk_tokens: int = 512   # hard cap before truncation
    min_chunk_lines: int = 3      # skip trivial single-line stubs

    # ──────────────────────────── Cache ────────────────────────────
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 3600
    query_cache_max_size: int = 1024   # in-memory LRU fallback size
    lru_index_cache_size: int = 8      # how many index snapshots to LRU-cache

    # ──────────────────────────── API ──────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    request_timeout_seconds: float = 30.0
    rate_limit_per_minute: int = 120

    # ──────────────────────────── Batch embedding ──────────────────
    embed_batch_size: int = 2
    embed_max_length: int = 512    # bge-small max token length

    # ──────────────────────────── MTEB ─────────────────────────────
    mteb_tasks: list[str] = ["AppsRetrieval"]
    mteb_output_dir: str = "results"


# Singleton
settings = Settings()

# Ensure directories exist
settings.indexes_dir.mkdir(parents=True, exist_ok=True)
settings.results_dir.mkdir(parents=True, exist_ok=True)
