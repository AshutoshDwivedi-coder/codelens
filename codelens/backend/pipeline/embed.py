"""
embed.py – Embedding service for CodeLens.

Wraps the PrePostPipelineEncoder and adds:
  - Content-hash–based embedding cache (skip re-embedding unchanged chunks)
  - Batch processing with progress reporting
  - FAISS index building (flat or HNSW)
  - Persistence: save/load index + chunk list
"""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("codelens.embed")

# ──────────────────────────── Optional FAISS ───────────────────────────────
try:
    import faiss
    _FAISS_AVAILABLE = True
except ImportError:
    _FAISS_AVAILABLE = False
    logger.warning(
        "faiss-cpu not installed. Install with: pip install faiss-cpu\n"
        "Dense index will use numpy brute-force fallback."
    )


class EmbeddingCache:
    """
    Disk-backed cache: content_hash → embedding vector.
    Avoids re-embedding unchanged chunks across incremental rebuilds.
    """

    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self._cache: dict[str, np.ndarray] = {}
        if cache_path.exists():
            self._load()

    def _load(self) -> None:
        try:
            with open(self.cache_path, "rb") as fh:
                self._cache = pickle.load(fh)
            logger.info("Embedding cache loaded: %d entries", len(self._cache))
        except Exception as exc:
            logger.warning("Could not load embedding cache: %s", exc)
            self._cache = {}

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "wb") as fh:
            pickle.dump(self._cache, fh)
        logger.info("Embedding cache saved: %d entries", len(self._cache))

    def get(self, content_hash: str) -> Optional[np.ndarray]:
        return self._cache.get(content_hash)

    def put(self, content_hash: str, vector: np.ndarray) -> None:
        self._cache[content_hash] = vector

    def __len__(self) -> int:
        return len(self._cache)


class DenseIndex:
    """
    Wraps a FAISS index (or numpy fallback) for ANN search.
    Stores chunk metadata alongside the vectors.
    """

    def __init__(self, dim: int, index_type: str = "flat") -> None:
        self.dim = dim
        self.index_type = index_type
        self.chunks: list[dict] = []          # ordered, parallel to FAISS ids
        self._index = self._build_empty_index(dim, index_type)
        self._np_matrix: Optional[np.ndarray] = None  # fallback

    # ──────────────────────────── Index building ──────────────────

    def _build_empty_index(self, dim: int, index_type: str):
        if not _FAISS_AVAILABLE:
            return None
        if index_type == "hnsw":
            index = faiss.IndexHNSWFlat(dim, 32)
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 50
        else:
            index = faiss.IndexFlatIP(dim)  # inner product on L2-normed = cosine
        return index

    def add(self, vectors: np.ndarray, chunk_dicts: list[dict]) -> None:
        """Add *vectors* (shape N×dim, float32, L2-normed) and their metadata."""
        assert vectors.shape[1] == self.dim, f"Dim mismatch: {vectors.shape[1]} vs {self.dim}"
        self.chunks.extend(chunk_dicts)

        if self._index is not None:
            self._index.add(vectors.astype(np.float32))
        else:
            # Numpy fallback
            if self._np_matrix is None:
                self._np_matrix = vectors.astype(np.float32)
            else:
                self._np_matrix = np.vstack([self._np_matrix, vectors.astype(np.float32)])

    def search(self, query_vec: np.ndarray, top_k: int = 100) -> list[tuple[float, dict]]:
        """
        Return list of (score, chunk_dict) ordered by descending cosine similarity.
        """
        q = query_vec.reshape(1, -1).astype(np.float32)

        if self._index is not None:
            scores, ids = self._index.search(q, min(top_k, len(self.chunks)))
            results = []
            for score, idx in zip(scores[0], ids[0]):
                if idx < 0 or idx >= len(self.chunks):
                    continue
                results.append((float(score), self.chunks[idx]))
            return results

        if self._np_matrix is not None and len(self.chunks) > 0:
            scores_np = (self._np_matrix @ q.T).flatten()
            top_idxs = np.argsort(scores_np)[::-1][:top_k]
            return [(float(scores_np[i]), self.chunks[i]) for i in top_idxs]

        return []

    # ──────────────────────────── Persistence ─────────────────────

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        # Save chunks
        with open(path / "chunks.json", "w", encoding="utf-8") as fh:
            json.dump(self.chunks, fh)
        # Save FAISS index
        if self._index is not None and _FAISS_AVAILABLE:
            faiss.write_index(self._index, str(path / "faiss.index"))
        elif self._np_matrix is not None:
            np.save(str(path / "vectors.npy"), self._np_matrix)
        # Save metadata
        meta = {"dim": self.dim, "index_type": self.index_type, "n_chunks": len(self.chunks)}
        with open(path / "index_meta.json", "w") as fh:
            json.dump(meta, fh)
        logger.info("Dense index saved to %s (%d chunks)", path, len(self.chunks))

    @classmethod
    def load(cls, path: Path) -> "DenseIndex":
        with open(path / "index_meta.json") as fh:
            meta = json.load(fh)
        inst = cls(dim=meta["dim"], index_type=meta["index_type"])
        with open(path / "chunks.json") as fh:
            inst.chunks = json.load(fh)
        faiss_path = path / "faiss.index"
        np_path = path / "vectors.npy"
        if faiss_path.exists() and _FAISS_AVAILABLE:
            inst._index = faiss.read_index(str(faiss_path))
        elif np_path.exists():
            inst._np_matrix = np.load(str(np_path))
        logger.info("Dense index loaded from %s (%d chunks)", path, len(inst.chunks))
        return inst

    def __len__(self) -> int:
        return len(self.chunks)


# ──────────────────────────── Indexing pipeline ────────────────────────────


def build_dense_index(
    chunks: list,                     # list of CodeChunk
    encoder,                          # PrePostPipelineEncoder
    cache: Optional[EmbeddingCache] = None,
    batch_size: int = 16,
    index_type: str = "flat",
    progress_callback: Optional[Any] = None,
) -> tuple[DenseIndex, int, int]:
    """
    Embed *chunks* and build a DenseIndex.

    Returns
    -------
    (index, n_embedded, n_cached)
    """
    from pipeline.normalize import normalize_document

    n_cached = 0
    n_embedded = 0
    all_vecs: list[np.ndarray] = []
    all_meta: list[dict] = []

    # Split into cached and to-embed
    to_embed_texts: list[str] = []
    to_embed_indices: list[int] = []
    cached_results: dict[int, np.ndarray] = {}

    for i, chunk in enumerate(chunks):
        ch = chunk.content_hash if hasattr(chunk, "content_hash") else hashlib.sha256(chunk.code.encode()).hexdigest()[:32]
        if cache is not None:
            cached_vec = cache.get(ch)
            if cached_vec is not None:
                cached_results[i] = cached_vec
                n_cached += 1
                continue
        text = normalize_document(
            chunk.code,
            symbol_name=getattr(chunk, "symbol_name", None),
            language=getattr(chunk, "language", None),
        )
        to_embed_texts.append(text)
        to_embed_indices.append(i)

    # Batch embed with live progress updates
    if to_embed_texts:
        total = len(to_embed_texts)
        logger.info("Embedding %d chunks (batch_size=%d)…", total, batch_size)
        t0 = time.perf_counter()
        batches = []
        for start_idx in range(0, total, batch_size):
            end_idx = min(start_idx + batch_size, total)
            batch = to_embed_texts[start_idx:end_idx]
            if progress_callback:
                progress_callback(f"Generating embeddings ({end_idx}/{total})…")
            vecs = encoder.encode(
                batch,
                prompt_type=None,  # already normalized
                batch_size=batch_size,
                show_progress_bar=False,
            )
            batches.append(vecs)
        new_vecs = np.vstack(batches)
        dt = time.perf_counter() - t0
        logger.info("Embedded %d chunks in %.1f s (%.0f chunks/s)",
                    total, dt, total / max(dt, 0.001))
        n_embedded = total

        # Store in cache
        for j, (idx, vec) in enumerate(zip(to_embed_indices, new_vecs)):
            if cache is not None:
                chunk = chunks[idx]
                ch = chunk.content_hash if hasattr(chunk, "content_hash") else hashlib.sha256(chunk.code.encode()).hexdigest()[:32]
                cache.put(ch, vec)
            cached_results[idx] = new_vecs[j]

    # Build final ordered list
    dim = next(iter(cached_results.values())).shape[0] if cached_results else 1
    index = DenseIndex(dim=dim, index_type=index_type)

    vecs_ordered = []
    metas_ordered = []
    for i, chunk in enumerate(chunks):
        vec = cached_results.get(i)
        if vec is None:
            continue
        vecs_ordered.append(vec)
        meta = {
            "chunk_id": getattr(chunk, "chunk_id", str(i)),
            "content_hash": getattr(chunk, "content_hash", ""),
            "lineage_id": getattr(chunk, "lineage_id", ""),
            "file_path": getattr(chunk, "file_path", ""),
            "symbol_name": getattr(chunk, "symbol_name", ""),
            "signature": getattr(chunk, "signature", ""),
            "docstring": getattr(chunk, "docstring", ""),
            "language": getattr(chunk, "language", ""),
            "chunk_type": getattr(chunk, "chunk_type", "block"),
            "start_line": getattr(chunk, "start_line", 1),
            "end_line": getattr(chunk, "end_line", 1),
            "code": getattr(chunk, "code", ""),
            "tags": getattr(chunk, "tags", {}),
        }
        metas_ordered.append(meta)

    if vecs_ordered:
        index.add(np.stack(vecs_ordered), metas_ordered)

    logger.info("Dense index built: %d chunks (%d new, %d cached)", len(index), n_embedded, n_cached)
    return index, n_embedded, n_cached
