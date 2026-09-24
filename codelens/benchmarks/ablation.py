"""
ablation.py – Ablation study for CodeLens retrieval pipeline.

Runs retrieval with different pipeline configurations and measures
NDCG@10 and MRR on a sample evaluation set, writing results to
results/ablation_results.json.

Usage:
    cd codelens/backend
    python benchmarks/ablation.py --sample-repo ../sample_repo
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from itertools import product
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger("codelens.ablation")

_BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))


# ──────────────────────────── Ablation configs ────────────────────────────

ABLATION_CONFIGS = [
    {"name": "dense_only",              "use_bm25": False, "use_hybrid": False, "use_rerank": False, "use_query_clean": False},
    {"name": "dense+clean",             "use_bm25": False, "use_hybrid": False, "use_rerank": False, "use_query_clean": True},
    {"name": "bm25_only",               "use_bm25": True,  "use_hybrid": False, "use_rerank": False, "use_query_clean": False},
    {"name": "hybrid_rrf",              "use_bm25": True,  "use_hybrid": True,  "use_rerank": False, "use_query_clean": False},
    {"name": "hybrid_rrf+clean",        "use_bm25": True,  "use_hybrid": True,  "use_rerank": False, "use_query_clean": True},
    {"name": "hybrid_rrf+rerank",       "use_bm25": True,  "use_hybrid": True,  "use_rerank": True,  "use_query_clean": False},
    {"name": "full_pipeline",           "use_bm25": True,  "use_hybrid": True,  "use_rerank": True,  "use_query_clean": True},
]

# Sample eval pairs (query → expected symbol name; used for MRR/NDCG@10)
SAMPLE_EVAL_PAIRS = [
    {"query": "sort a list", "relevant": "sort_list"},
    {"query": "parse json data", "relevant": "parse_json"},
    {"query": "http get request", "relevant": "http_request"},
    {"query": "connect to database", "relevant": "connect_db"},
    {"query": "calculate fibonacci", "relevant": "fibonacci"},
]


def dcg_at_k(relevances: list[int], k: int) -> float:
    import math
    result = 0.0
    for i, rel in enumerate(relevances[:k]):
        result += rel / math.log2(i + 2)
    return result


def ndcg_at_k(relevances: list[int], k: int) -> float:
    ideal = sorted(relevances, reverse=True)
    ideal_dcg = dcg_at_k(ideal, k)
    if ideal_dcg == 0:
        return 0.0
    return dcg_at_k(relevances, k) / ideal_dcg


def mrr(relevances: list[int]) -> float:
    for i, rel in enumerate(relevances):
        if rel > 0:
            return 1.0 / (i + 1)
    return 0.0


def run_ablation(index_dir: Path, output_dir: Path) -> dict:
    """
    Run ablation study using the indexed data.
    Requires at least one indexed version to exist.
    """
    from pipeline.embed import DenseIndex
    from pipeline.bm25 import BM25Index
    from pipeline.query import clean_query
    from pipeline.fusion import reciprocal_rank_fusion
    from pipeline.rerank import rerank
    from encoder import PrePostPipelineEncoder
    try:
        from mteb.encoder_interface import PromptType
    except ImportError:
        try:
            from mteb import PromptType
        except ImportError:
            class PromptType:
                query = "query"
                passage = "passage"

    # Load the most recent index
    snapshots = sorted(index_dir.iterdir(), reverse=True)
    snap_dir = None
    for s in snapshots:
        if (s / "manifest.json").exists():
            snap_dir = s
            break

    if snap_dir is None:
        logger.error("No indexed snapshot found in %s", index_dir)
        return {}

    logger.info("Loading indexes from %s", snap_dir)
    dense_idx = DenseIndex.load(snap_dir)
    bm25_idx = BM25Index.load(snap_dir)
    encoder = PrePostPipelineEncoder(model_name="BAAI/bge-small-en-v1.5")

    results_table = []

    for cfg in ABLATION_CONFIGS:
        logger.info("Running config: %s", cfg["name"])
        ndcg_scores = []
        mrr_scores = []
        latencies = []

        for pair in SAMPLE_EVAL_PAIRS:
            query = pair["query"]
            relevant_sym = pair["relevant"]
            t0 = time.perf_counter()

            # Clean query
            if cfg["use_query_clean"]:
                cleaned = clean_query(query).cleaned
            else:
                cleaned = query

            # Embed
            q_vec = encoder.encode([cleaned], prompt_type=PromptType.query, show_progress_bar=False)[0]

            # Retrieve
            dense_res = dense_idx.search(q_vec, top_k=50)
            bm25_res = bm25_idx.search(cleaned, top_k=50) if cfg["use_bm25"] else []

            # Fuse
            if cfg["use_hybrid"] and bm25_res and dense_res:
                fused = reciprocal_rank_fusion([bm25_res, dense_res])
            elif dense_res:
                fused = dense_res
            else:
                fused = []

            # Rerank
            if cfg["use_rerank"] and fused:
                fused = rerank(cleaned, fused, top_k=20)

            latencies.append((time.perf_counter() - t0) * 1000)

            # Score
            relevances = [
                1 if c.get("symbol_name", "") == relevant_sym else 0
                for _, c in fused[:10]
            ]
            ndcg_scores.append(ndcg_at_k(relevances, 10))
            mrr_scores.append(mrr(relevances))

        avg_ndcg = round(sum(ndcg_scores) / len(ndcg_scores), 4) if ndcg_scores else 0
        avg_mrr = round(sum(mrr_scores) / len(mrr_scores), 4) if mrr_scores else 0
        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0

        row = {
            "config": cfg["name"],
            "use_bm25": cfg["use_bm25"],
            "use_hybrid": cfg["use_hybrid"],
            "use_rerank": cfg["use_rerank"],
            "use_query_clean": cfg["use_query_clean"],
            "ndcg_at_10": avg_ndcg,
            "mrr": avg_mrr,
            "avg_latency_ms": avg_latency,
            "note": "Measured on sample_eval_pairs (not MTEB AppsRetrieval)",
        }
        results_table.append(row)
        logger.info("  NDCG@10=%.4f  MRR=%.4f  Latency=%.1fms", avg_ndcg, avg_mrr, avg_latency)

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Ablation on sample eval set. Run run_mteb.py for official MTEB numbers.",
        "configs": results_table,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "ablation_results.json"
    with open(out_path, "w") as fh:
        json.dump(output, fh, indent=2)
    logger.info("Ablation results written to %s", out_path)
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index-dir", default=str(_BACKEND.parent / "indexes"))
    p.add_argument("--output-dir", default=str(_BACKEND.parent / "results"))
    args = p.parse_args()
    run_ablation(Path(args.index_dir), Path(args.output_dir))


if __name__ == "__main__":
    main()
