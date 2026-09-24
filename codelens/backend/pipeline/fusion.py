"""
fusion.py – Reciprocal Rank Fusion (RRF) for hybrid retrieval.

Combines ranked lists from BM25 and dense search into a single fused ranking.
Each result gets a fused score = sum(1 / (k + rank_in_list)) over all lists.

Also provides a confidence check: if the top result's fused score is much
higher than the second, reranking may be skipped.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("codelens.fusion")

# Standard RRF constant (as in the original RRF paper)
DEFAULT_K = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[float, dict]]],
    k: int = DEFAULT_K,
    weights: Optional[list[float]] = None,
) -> list[tuple[float, dict]]:
    """
    Fuse multiple ranked lists using Reciprocal Rank Fusion.

    Parameters
    ----------
    ranked_lists:  list of (score, chunk_dict) lists, each sorted desc by score
    k:             RRF constant (default 60)
    weights:       per-list weight multipliers (default: all 1.0)

    Returns
    -------
    Fused list of (fused_score, chunk_dict), sorted descending.
    Chunk dicts are enriched with 'bm25_rank', 'dense_rank' fields.
    """
    if not ranked_lists:
        return []

    if weights is None:
        weights = [1.0] * len(ranked_lists)
    assert len(weights) == len(ranked_lists)

    # Map chunk_id → (fused_score, chunk_dict)
    fused: dict[str, list] = {}

    for list_idx, (ranked, weight) in enumerate(zip(ranked_lists, weights)):
        list_name = ["bm25", "dense", "list2", "list3"][min(list_idx, 3)]
        for rank, (score, chunk) in enumerate(ranked):
            cid = chunk.get("chunk_id", "")
            rrf_score = weight / (k + rank + 1)

            if cid not in fused:
                chunk = dict(chunk)  # copy to avoid mutation
                chunk["_rrf_contributions"] = {}
                chunk["_orig_scores"] = {}
                fused[cid] = [0.0, chunk]

            fused[cid][0] += rrf_score
            fused[cid][1]["_rrf_contributions"][list_name] = rrf_score
            fused[cid][1]["_orig_scores"][list_name] = float(score)
            fused[cid][1][f"{list_name}_rank"] = rank + 1

    # Sort descending by fused score
    results = sorted(fused.values(), key=lambda x: x[0], reverse=True)

    # Flatten and add fused_score to chunk dict
    output: list[tuple[float, dict]] = []
    for fused_score, chunk in results:
        chunk = dict(chunk)
        chunk["fused_score"] = round(fused_score, 6)
        output.append((fused_score, chunk))

    return output


def high_confidence(
    fused: list[tuple[float, dict]],
    margin_threshold: float = 0.15,
) -> bool:
    """
    Return True if the top result's fused score is significantly higher
    than the second (indicating reranking may not be necessary).
    """
    if len(fused) < 2:
        return True
    top_score = fused[0][0]
    second_score = fused[1][0]
    if top_score == 0:
        return False
    margin = (top_score - second_score) / top_score
    return margin >= margin_threshold
