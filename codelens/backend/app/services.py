"""
services.py – Stateful search service singleton for CodeLens.

Manages:
  - LRU-cached index loading (dense + BM25) per version
  - The full query pipeline (clean → embed → BM25 ‖ dense → RRF → rerank → collapse)
  - Per-stage timing instrumentation
  - Index building from a git repository
"""
from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("codelens.services")

# ──────────────────────────── Lazy encoder singleton ─────────────────────

_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        from app.config import settings
        from encoder import PrePostPipelineEncoder
        _encoder = PrePostPipelineEncoder(
            model_name=settings.embed_model,
            use_query_clean=settings.use_query_clean,
            use_doc_normalize=settings.use_doc_normalize,
            batch_size=settings.embed_batch_size,
            max_length=settings.embed_max_length,
        )
    return _encoder


# ──────────────────────────── Index LRU cache ─────────────────────────────

_index_cache: dict[str, dict] = {}  # version → {"dense": DenseIndex, "bm25": BM25Index}
_index_access: list[str] = []       # LRU order
_MAX_CACHED_VERSIONS = 8


def _load_index(version: str) -> Optional[dict]:
    """Load (dense + BM25) index for *version*. Returns None if not found."""
    from app.config import settings
    from pipeline.embed import DenseIndex
    from pipeline.bm25 import BM25Index
    from pipeline.versioning import get_version_manager

    vm = get_version_manager()

    # Resolve "latest" to the newest snapshot
    if version in ("latest", ""):
        snapshots = vm.list_snapshots()
        if not snapshots:
            logger.warning("No indexed versions available")
            return None
        version = snapshots[0]["commit_sha"]

    snap_dir = vm.snapshot_dir(version)
    if not snap_dir.exists():
        logger.warning("Snapshot not found for version: %s", version)
        return None

    index_data: dict = {"version": version, "dense": None, "bm25": None}

    # Load dense index
    try:
        index_data["dense"] = DenseIndex.load(snap_dir)
        logger.info("Dense index loaded for %s (%d chunks)", version, len(index_data["dense"]))
    except Exception as exc:
        logger.warning("Could not load dense index for %s: %s", version, exc)

    # Load BM25 index
    try:
        index_data["bm25"] = BM25Index.load(snap_dir)
        logger.info("BM25 index loaded for %s (%d docs)", version, len(index_data["bm25"]))
    except Exception as exc:
        logger.warning("Could not load BM25 index for %s: %s", version, exc)

    return index_data


def _get_index(version: str) -> Optional[dict]:
    """LRU-cached index retrieval."""
    if version in _index_cache:
        # Move to front (most recently used)
        _index_access.remove(version)
        _index_access.append(version)
        return _index_cache[version]

    data = _load_index(version)
    if data is None:
        return None

    _index_cache[version] = data
    _index_access.append(version)

    # Evict oldest if over capacity
    while len(_index_access) > _MAX_CACHED_VERSIONS:
        oldest = _index_access.pop(0)
        del _index_cache[oldest]
        logger.debug("Evicted index for version: %s", oldest)

    return data


# ──────────────────────────── Search service ──────────────────────────────


class SearchService:
    """
    Stateless search service (one per process; index is LRU-cached).
    """

    def __init__(self) -> None:
        pass

    async def search(
        self,
        query: str,
        version: str = "latest",
        lang_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        top_k: int = 10,
        config_overrides: Optional[dict] = None,
        timings: Optional[dict] = None,
    ) -> dict:
        """Execute the full retrieval pipeline, returning ranked results."""
        if config_overrides is None:
            config_overrides = {}
        if timings is None:
            timings = {}
        from app.config import settings
        from app.cache import get_cache, make_query_cache_key, config_hash
        from pipeline.query import clean_query
        from pipeline.fusion import reciprocal_rank_fusion, high_confidence
        from pipeline.rerank import rerank
        from pipeline.lineage import group_by_lineage

        # Merge config overrides
        cfg = {
            "use_bm25": settings.use_bm25,
            "use_hybrid": settings.use_hybrid,
            "use_rerank": settings.use_rerank,
            "use_query_clean": settings.use_query_clean,
            "use_version_collapse": settings.use_version_collapse,
            "use_second_pass": settings.use_second_pass,
            "bm25_top_k": settings.bm25_top_k,
            "dense_top_k": settings.dense_top_k,
            "rerank_top_k": settings.rerank_top_k,
            "final_top_k": top_k,
        }
        cfg.update(config_overrides)

        # 1. Cache check
        cache = get_cache(redis_url=settings.redis_url)
        cache_key = make_query_cache_key(query, version, config_hash(cfg))
        t0 = time.perf_counter()
        cached = cache.get(cache_key)
        timings["cache_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        if cached is not None:
            logger.info("Cache hit for query: %.40s…", query)
            return cached

        # 2. Load index
        index_data = _get_index(version)
        if index_data is None:
            return {
                "query": query,
                "cleaned_query": query,
                "query_type": "general",
                "version": version,
                "total_results": 0,
                "results": [],
                "config_used": cfg,
            }

        resolved_version = index_data["version"]
        dense_idx = index_data.get("dense")
        bm25_idx = index_data.get("bm25")

        # 3. Query cleaning
        t0 = time.perf_counter()
        if cfg["use_query_clean"]:
            cq = clean_query(query)
            cleaned = cq.cleaned
            query_type = cq.query_type.value
        else:
            cleaned = query
            query_type = "general"
        timings["query_clean_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        # 4. Embed query
        t0 = time.perf_counter()
        enc = _get_encoder()
        try:
            q_vec = enc.encode([cleaned], show_progress_bar=False)[0]
        except Exception as _enc_err:
            logger.warning("Encoder error: %s", _enc_err)
            # Fallback: return empty results if encoder fails
            return {
                "query": query,
                "cleaned_query": cleaned,
                "query_type": query_type,
                "version": version,
                "total_results": 0,
                "results": [],
                "config_used": cfg,
            }
        timings["embed_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        # 5. BM25 search
        bm25_results: list = []
        t0 = time.perf_counter()
        if cfg["use_bm25"] and bm25_idx is not None:
            bm25_results = bm25_idx.search(cleaned, top_k=cfg["bm25_top_k"])
        timings["bm25_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        # 6. Dense search
        dense_results: list = []
        t0 = time.perf_counter()
        if dense_idx is not None:
            dense_results = dense_idx.search(q_vec, top_k=cfg["dense_top_k"])
        timings["dense_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        # 7. Fusion (RRF or dense-only)
        t0 = time.perf_counter()
        if cfg["use_hybrid"] and bm25_results and dense_results:
            fused = reciprocal_rank_fusion([bm25_results, dense_results])
        elif dense_results:
            fused = [(s, dict(c)) for s, c in dense_results]
            for s, c in fused:
                c["fused_score"] = float(s)
        elif bm25_results:
            fused = [(s, dict(c)) for s, c in bm25_results]
            for s, c in fused:
                c["fused_score"] = float(s)
        else:
            fused = []
        timings["fusion_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        # 8. Apply language / type filters
        if lang_filter:
            fused = [(s, c) for s, c in fused if c.get("language", "").lower() == lang_filter.lower()]
        if type_filter:
            fused = [(s, c) for s, c in fused if c.get("chunk_type", "").lower() == type_filter.lower()]

        # 9. Rerank
        t0 = time.perf_counter()
        rerank_top = min(cfg["rerank_top_k"], len(fused))
        if cfg["use_rerank"] and fused and not high_confidence(fused):
            from app.config import settings as _s
            fused = rerank(cleaned, fused, top_k=rerank_top, model_name=_s.reranker_model)
        timings["rerank_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        # 10. Version collapse
        if cfg["use_version_collapse"]:
            fused = group_by_lineage(fused, version_collapse=True)

        # 11. Trim to final_top_k
        final = fused[: cfg["final_top_k"]]

        result = {
            "query": query,
            "cleaned_query": cleaned,
            "query_type": query_type,
            "version": resolved_version,
            "total_results": len(fused),
            "results": [c for _, c in final],
            "config_used": cfg,
        }

        # Cache result
        cache.set(cache_key, result)
        return result

    def get_chunk(self, chunk_id: str, version: str = "latest") -> Optional[dict]:
        """Retrieve a single chunk by ID."""
        idx_data = _get_index(version)
        if idx_data is None:
            return None
        dense = idx_data.get("dense")
        if dense is None:
            return None
        for chunk in dense.chunks:
            if chunk.get("chunk_id") == chunk_id:
                return chunk
        return None


# ──────────────────────────── Index builder ───────────────────────────────


def build_index_for_repo(
    repo_path: str,
    commit_sha: Optional[str] = None,
    force_full: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Build or incrementally update the index for a git repository.

    Returns the manifest dict.
    """
    import subprocess
    from app.config import settings
    from pipeline.chunking import chunk_file, detect_language, EXTENSION_TO_LANG
    from pipeline.embed import DenseIndex, EmbeddingCache, build_dense_index
    from pipeline.bm25 import BM25Index
    from pipeline.versioning import get_version_manager
    from pipeline.tagging import tag_chunk

    def _progress(msg: str):
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    repo = Path(repo_path)
    if not repo.exists():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    vm = get_version_manager()

    # Resolve commit SHA
    if commit_sha is None:
        commit_sha = vm.get_current_commit(str(repo))
    if commit_sha == "unknown":
        # Not a git repo; use a synthetic SHA
        import hashlib
        commit_sha = "local-" + hashlib.sha256(str(repo).encode()).hexdigest()[:8]

    _progress(f"Indexing commit {commit_sha[:7]}…")

    # Determine files to process
    if not force_full and vm.has_snapshot(commit_sha):
        _progress("Snapshot already exists; nothing to do.")
        return vm.read_manifest(commit_sha)

    # Find previous snapshot for incremental rebuild
    snapshots = vm.list_snapshots()
    prev_sha = snapshots[0]["commit_sha"] if snapshots else None
    changed_files: Optional[set[str]] = None

    if prev_sha and not force_full and prev_sha != commit_sha:
        changed_paths = vm.get_changed_files(str(repo), prev_sha, commit_sha)
        if changed_paths:
            changed_files = set(changed_paths)
            _progress(f"Incremental rebuild: {len(changed_files)} changed files")
        else:
            _progress("No changed files; nothing to do.")
            return vm.read_manifest(prev_sha) or {}

    # Collect source files
    supported_exts = set(EXTENSION_TO_LANG.keys())
    all_files = [
        f for f in repo.rglob("*")
        if f.is_file()
        and f.suffix.lower() in supported_exts
        and not any(p in str(f) for p in [".git", "node_modules", "__pycache__", ".venv", "venv"])
    ]

    if changed_files is not None:
        # Only process changed files
        all_files = [f for f in all_files if str(f.relative_to(repo)) in changed_files]

    _progress(f"Chunking {len(all_files)} files…")
    all_chunks = []
    for fpath in all_files:
        try:
            source = fpath.read_text(encoding="utf-8", errors="replace")
            rel_path = str(fpath.relative_to(repo))
            lang = detect_language(str(fpath))
            chunks = chunk_file(source, rel_path, language=lang,
                                max_chunk_tokens=settings.max_chunk_tokens,
                                min_chunk_lines=settings.min_chunk_lines)
            for c in chunks:
                c.tags.update(tag_chunk(c, rel_path))
            all_chunks.extend(chunks)
        except Exception as exc:
            logger.warning("Error chunking %s: %s", fpath, exc)

    _progress(f"Total chunks: {len(all_chunks)}")

    if not all_chunks:
        _progress("No chunks produced; check supported file types.")
        return {}

    # Embedding cache
    cache_path = settings.indexes_dir / "embed_cache.pkl"
    emb_cache = EmbeddingCache(cache_path)

    encoder = _get_encoder()
    t_build_start = time.time()

    # Build dense index
    _progress("Building dense index…")
    snap_dir = vm.snapshot_dir(commit_sha)
    dense_idx, n_embedded, n_cached = build_dense_index(
        all_chunks, encoder, cache=emb_cache,
        batch_size=settings.embed_batch_size,
        index_type=settings.faiss_index_type,
    )
    dense_idx.save(snap_dir)
    emb_cache.save()

    # Build BM25 index
    _progress("Building BM25 index…")
    bm25_idx = BM25Index()
    bm25_idx.build(all_chunks)
    bm25_idx.save(snap_dir)

    build_time = time.time() - t_build_start
    _progress(f"Index built in {build_time:.1f}s ({n_embedded} embedded, {n_cached} cached)")

    commit_msg = vm.get_commit_message(str(repo), commit_sha)
    manifest = vm.write_manifest(
        commit_sha=commit_sha,
        chunk_count=len(all_chunks),
        model_name=encoder.model_name,
        build_time_seconds=build_time,
        n_embedded=n_embedded,
        n_cached=n_cached,
        commit_message=commit_msg,
    )

    # Invalidate cached index for this version
    if commit_sha in _index_cache:
        del _index_cache[commit_sha]
        if commit_sha in _index_access:
            _index_access.remove(commit_sha)

    return manifest


# ──────────────────────────── Singleton ───────────────────────────────────

_search_service: Optional[SearchService] = None


def get_search_service() -> Optional[SearchService]:
    """Return the SearchService; None if no index is loaded yet."""
    global _search_service
    # Always return a service; it will 503 if no index is available
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
