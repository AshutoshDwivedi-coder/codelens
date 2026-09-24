"""
rerank.py – Cross-encoder reranker for CodeLens.

Uses a small cross-encoder model (default: ms-marco-MiniLM-L-6-v2) to
rescore the top-K fused candidates.  The reranker sees both the query
and the code chunk as input and produces a relevance score.

Graceful fallback: if the model is unavailable or the system is under
load, reranking is skipped and fused scores are used directly.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger("codelens.rerank")

try:
    from sentence_transformers.cross_encoder import CrossEncoder
    _CE_AVAILABLE = True
except ImportError:
    _CE_AVAILABLE = False
    logger.warning(
        "sentence-transformers not installed; cross-encoder reranking unavailable."
    )

# Default cross-encoder model (small, fast on CPU)
DEFAULT_RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker_instance: Optional["CrossEncoder"] = None


def _get_reranker(model_name: str = DEFAULT_RERANKER) -> Optional["CrossEncoder"]:
    global _reranker_instance
    if not _CE_AVAILABLE:
        return None
    if _reranker_instance is None:
        try:
            logger.info("Loading cross-encoder: %s", model_name)
            _reranker_instance = CrossEncoder(model_name, max_length=512)
            logger.info("Cross-encoder loaded")
        except Exception as exc:
            logger.warning("Could not load cross-encoder (%s); reranking disabled", exc)
            return None
    return _reranker_instance


def rerank(
    query: str,
    candidates: list[tuple[float, dict]],
    top_k: int = 30,
    model_name: str = DEFAULT_RERANKER,
    timeout_seconds: float = 10.0,
) -> list[tuple[float, dict]]:
    """
    Rerank *candidates* using a cross-encoder.

    Parameters
    ----------
    query:       original (cleaned) query string
    candidates:  list of (score, chunk_dict) from fusion step
    top_k:       number of candidates to rerank (rest are kept in order)
    model_name:  cross-encoder model name
    timeout_seconds: if reranking takes longer, fall back to fused order

    Returns
    -------
    Reranked list of (rerank_score, chunk_dict).
    """
    ce = _get_reranker(model_name)
    if ce is None:
        # Add rerank_score = fused_score as passthrough
        result = []
        for score, chunk in candidates:
            chunk = dict(chunk)
            chunk["rerank_score"] = chunk.get("fused_score", score)
            result.append((score, chunk))
        return result

    rerank_candidates = candidates[:top_k]
    passthrough = candidates[top_k:]

    # Build (query, code) pairs
    pairs = []
    for _, chunk in rerank_candidates:
        code_text = (chunk.get("symbol_name", "") + "\n" + chunk.get("code", ""))[:1000]
        pairs.append((query, code_text))

    t0 = time.perf_counter()
    try:
        scores = ce.predict(pairs, show_progress_bar=False)
        elapsed = time.perf_counter() - t0

        if elapsed > timeout_seconds:
            logger.warning("Reranking timed out (%.1f s); using fused order", elapsed)
            return _passthrough_scores(candidates)

    except Exception as exc:
        logger.warning("Reranking failed (%s); using fused order", exc)
        return _passthrough_scores(candidates)

    # Merge scores back
    reranked = []
    for (fused_score, chunk), rerank_score in zip(rerank_candidates, scores):
        chunk = dict(chunk)
        chunk["rerank_score"] = float(rerank_score)
        reranked.append((float(rerank_score), chunk))

    # Sort reranked candidates descending
    reranked.sort(key=lambda x: x[0], reverse=True)

    # Append passthrough with rerank_score = fused_score
    for fused_score, chunk in passthrough:
        chunk = dict(chunk)
        chunk["rerank_score"] = chunk.get("fused_score", fused_score)
        reranked.append((fused_score, chunk))

    return reranked


def _passthrough_scores(candidates: list[tuple[float, dict]]) -> list[tuple[float, dict]]:
    result = []
    for score, chunk in candidates:
        chunk = dict(chunk)
        chunk["rerank_score"] = chunk.get("fused_score", score)
        result.append((score, chunk))
    return result
