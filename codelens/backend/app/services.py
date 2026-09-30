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

    index_data: dict = {"version": version, "dense": None, "bm25": None, "manifest": None}

    try:
        index_data["manifest"] = vm.read_manifest(version)
    except Exception:
        pass

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


def _snapshot_matches_name(snap: dict, name_norm: str) -> bool:
    snap_name = (snap.get("repo_name") or "").lower()
    snap_path = (snap.get("repo_path") or "").replace("\\", "/").lower()
    snap_basename = Path(snap_path).name.lower() if snap_path else ""
    # A repository selected from a GitHub URL can arrive as either the full URL
    # or its final path component (for example, "owner/repo.git" or
    # "repo.git"). Snapshots use the cloned folder name, so normalise the
    # display-only Git suffix before comparing identities.
    normalized_filter = name_norm.rstrip("/")
    if normalized_filter.endswith(".git"):
        normalized_filter = normalized_filter[:-4]
    filter_basename = Path(normalized_filter).name
    return (
        normalized_filter == snap_name
        or normalized_filter == snap_basename
        or (normalized_filter and normalized_filter in snap_path)
        or snap_name.endswith(normalized_filter)
        or filter_basename == snap_basename
        or snap_name.endswith(filter_basename)
    )


def resolve_repo_version(repo_filter: Optional[str]) -> Optional[str]:
    """
    Map a repo name / id / path filter to the best matching snapshot commit SHA.
    Returns None when filter is empty or no matching snapshot exists.
    """
    versions = resolve_search_versions(repo_filter)
    return versions[0] if versions and repo_filter and repo_filter.strip().lower() not in ("all", "") else (
        versions[0] if versions else None
    )


def resolve_search_versions(repo_filter: Optional[str] = None) -> list[str]:
    """
    Latest snapshot id per repository to search.

    Empty / "all" → one snapshot per indexed repo.
    Named filter → matching repos only (comma-separated).
    """
    from pipeline.versioning import get_version_manager

    vm = get_version_manager()
    snapshots = vm.list_snapshots()
    names: list[str] = []
    if repo_filter and repo_filter.strip().lower() not in ("all", ""):
        names = [n.strip().lower().replace("\\", "/") for n in repo_filter.split(",") if n.strip()]

    seen_repos: set[str] = set()
    versions: list[str] = []
    for snap in snapshots:
        sha = snap.get("commit_sha")
        if not sha:
            continue
        repo_key = (snap.get("repo_name") or Path(snap.get("repo_path") or "").name or sha).lower()
        if repo_key in seen_repos:
            continue
        if names and not any(_snapshot_matches_name(snap, n) for n in names):
            continue
        seen_repos.add(repo_key)
        versions.append(sha)
    return versions


def _chunk_matches_repo(chunk: dict, repo_names: list[str], repo_paths: list[str]) -> bool:
    """Return True if chunk belongs to one of the requested repos."""
    tags = chunk.get("tags") or {}
    c_repo = (chunk.get("repo_name") or tags.get("repo_name") or "").lower()
    c_path = (chunk.get("file_path") or "").replace("\\", "/").lower()
    for name in repo_names:
        if name and (name == c_repo or name in c_path or c_path.startswith(name + "/")):
            return True
    for rpath in repo_paths:
        if rpath and rpath in c_path:
            return True
    # If chunk has no repo metadata, keep it when we already resolved the index snapshot
    if not c_repo:
        return True
    return False


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
        repo_filter: Optional[str] = None,
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

        # Prefer snapshots that belong to the selected repository (or all repos)
        repo_snapshot_missing = False
        search_versions: list[str] = []
        if version in ("latest", "", None):
            search_versions = resolve_search_versions(repo_filter)
            if search_versions:
                version = search_versions[0]
            elif repo_filter and repo_filter.strip().lower() not in ("all", ""):
                repo_snapshot_missing = True
        else:
            search_versions = [version]

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
            "repo_filter": repo_filter or "",
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

        if repo_snapshot_missing:
            return {
                "query": query,
                "cleaned_query": query,
                "query_type": "general",
                "version": version,
                "total_results": 0,
                "results": [],
                "config_used": cfg,
                "error": f"Repository {repo_filter!r} is not indexed. Index it first via POST /api/index.",
            }

        # 2–7. Clean, embed, then retrieve from one or more repo snapshots
        t0 = time.perf_counter()
        if cfg["use_query_clean"]:
            cq = clean_query(query)
            cleaned = cq.cleaned
            query_type = cq.query_type.value
        else:
            cleaned = query
            query_type = "general"
        timings["query_clean_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        t0 = time.perf_counter()
        enc = _get_encoder()
        try:
            import numpy as np
            q_vec = np.asarray(enc.encode([cleaned], show_progress_bar=False)[0], dtype=np.float32)
        except Exception as _enc_err:
            logger.warning("Encoder error: %s", _enc_err)
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

        if not search_versions:
            search_versions = [version]

        fused: list = []
        bm25_ms_acc = 0.0
        dense_ms_acc = 0.0
        fusion_ms_acc = 0.0
        resolved_version = version

        for snap_ver in search_versions:
            try:
                index_data = _get_index(snap_ver)
            except Exception as exc:
                logger.warning("Failed to load index %s: %s", snap_ver, exc)
                continue
            if index_data is None:
                continue
            resolved_version = index_data["version"]
            dense_idx = index_data.get("dense")
            bm25_idx = index_data.get("bm25")
            manifest = index_data.get("manifest") or {}

            t0 = time.perf_counter()
            bm25_results: list = []
            try:
                if cfg["use_bm25"] and bm25_idx is not None:
                    bm25_results = bm25_idx.search(cleaned, top_k=cfg["bm25_top_k"])
            except Exception as exc:
                logger.warning("BM25 search failed for %s: %s", snap_ver, exc)
            bm25_ms_acc += (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            dense_results: list = []
            try:
                if dense_idx is not None:
                    dense_results = dense_idx.search(q_vec, top_k=cfg["dense_top_k"])
            except Exception as exc:
                logger.warning("Dense search failed for %s: %s", snap_ver, exc)
            dense_ms_acc += (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            if cfg["use_hybrid"] and bm25_results and dense_results:
                local_fused = reciprocal_rank_fusion([bm25_results, dense_results])
            elif dense_results:
                local_fused = [(s, dict(c)) for s, c in dense_results]
                for s, c in local_fused:
                    c["fused_score"] = float(s)
            elif bm25_results:
                local_fused = [(s, dict(c)) for s, c in bm25_results]
                for s, c in local_fused:
                    c["fused_score"] = float(s)
            else:
                local_fused = []
            fusion_ms_acc += (time.perf_counter() - t0) * 1000

            repo_label = manifest.get("repo_name") or ""
            for s, c in local_fused:
                tags = c.get("tags") or {}
                if not c.get("repo_name"):
                    c["repo_name"] = tags.get("repo_name") or repo_label
                fused.append((s, c))

        timings["bm25_ms"] = round(bm25_ms_acc, 1)
        timings["dense_ms"] = round(dense_ms_acc, 1)
        timings["fusion_ms"] = round(fusion_ms_acc, 1)

        if len(search_versions) > 1 and fused:
            fused.sort(key=lambda pair: float(pair[0]), reverse=True)

        # 8. Apply language / type filters (repo already scoped via snapshots)
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

    repo = Path(repo_path).resolve()
    if not repo.exists():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    vm = get_version_manager()

    # Resolve underlying git commit (may be the parent monorepo HEAD)
    if commit_sha is None:
        commit_sha = vm.get_current_commit(str(repo))

    git_toplevel = vm.get_git_toplevel(str(repo))
    nested_in_other_git = False
    if git_toplevel:
        try:
            nested_in_other_git = Path(git_toplevel).resolve() != repo
        except Exception:
            nested_in_other_git = True

    if commit_sha == "unknown" or nested_in_other_git:
        # Standalone folder or nested demo inside a monorepo — unique path-based id
        import hashlib
        commit_sha = "local-" + hashlib.sha256(str(repo).encode()).hexdigest()[:12]

    # Namespace snapshot dirs by repo name so demos never overwrite each other
    original_commit = commit_sha
    snapshot_id = vm.make_snapshot_id(str(repo), commit_sha)

    _progress(f"Indexing {repo.name} ({snapshot_id[:40]}…)…")

    # Determine files to process
    if not force_full and vm.has_snapshot(snapshot_id):
        _progress("Snapshot already exists; nothing to do.")
        return vm.read_manifest(snapshot_id)

    # Find previous snapshot for THIS repo only (incremental rebuild)
    snapshots = [
        s for s in vm.list_snapshots()
        if (s.get("repo_name") or "").lower() == repo.name.lower()
        or (s.get("repo_path") or "").replace("\\", "/").lower().endswith("/" + repo.name.lower())
    ]
    prev_sha = snapshots[0]["commit_sha"] if snapshots else None
    changed_files: Optional[set[str]] = None

    if prev_sha and not force_full and prev_sha != snapshot_id and not nested_in_other_git:
        changed_paths = vm.get_changed_files(str(repo), snapshots[0].get("original_commit", prev_sha), original_commit)
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
            rel_path = str(fpath.relative_to(repo)).replace("\\", "/")
            lang = detect_language(str(fpath))
            chunks = chunk_file(source, rel_path, language=lang,
                                max_chunk_tokens=settings.max_chunk_tokens,
                                min_chunk_lines=settings.min_chunk_lines)
            for c in chunks:
                c.tags.update(tag_chunk(c, rel_path))
                c.tags["repo_name"] = repo.name
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
    snap_dir = vm.snapshot_dir(snapshot_id)
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

    commit_msg = vm.get_commit_message(str(repo), original_commit) if not nested_in_other_git else f"Index of {repo.name}"
    manifest = vm.write_manifest(
        commit_sha=snapshot_id,
        chunk_count=len(all_chunks),
        model_name=encoder.model_name,
        build_time_seconds=build_time,
        n_embedded=n_embedded,
        n_cached=n_cached,
        commit_message=commit_msg,
        repo_path=str(repo),
        repo_name=repo.name,
        original_commit=original_commit,
    )

    # Invalidate cached index for this version
    if snapshot_id in _index_cache:
        del _index_cache[snapshot_id]
        if snapshot_id in _index_access:
            _index_access.remove(snapshot_id)

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
