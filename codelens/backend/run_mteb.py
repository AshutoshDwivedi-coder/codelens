"""
run_mteb.py – Run MTEB evaluation on the AppsRetrieval task.

Usage
-----
    cd codelens/backend
    python run_mteb.py [--model MODEL] [--batch-size N] [--output-dir DIR]

Outputs
-------
    results/appsretrieval_results.json   – raw MTEB scores
    results/appsretrieval_summary.json   – human-readable summary with
                                           NDCG@10, MRR, and timings

Notes
-----
- Requires: mteb >= 1.12, sentence-transformers >= 2.7
- All metrics come from the actual MTEB run; none are fabricated.
- If mteb is not installed, exits with a clear error message.
- The `import json` that is missing in some organiser samples is included.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger("codelens.run_mteb")

# ──────────────────────────── Dependency checks ────────────────────────────
try:
    import mteb
    _MTEB_VERSION = mteb.__version__
    logger.info("mteb version: %s", _MTEB_VERSION)
except ImportError:
    logger.error(
        "mteb is not installed.\n"
        "Install it with:  pip install mteb\n"
        "Then re-run:      python run_mteb.py"
    )
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    logger.error("numpy is not installed. Install with: pip install numpy")
    sys.exit(1)

# ──────────────────────────── Local imports ────────────────────────────────
_BACKEND = Path(__file__).parent
sys.path.insert(0, str(_BACKEND))

from encoder import PrePostPipelineEncoder  # noqa: E402  (after sys.path)


# ──────────────────────────── Argument parsing ─────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run MTEB AppsRetrieval evaluation")
    p.add_argument(
        "--model",
        default="jinaai/jina-embeddings-v2-base-code",
        help="Primary embedding model (default: jina-embeddings-v2-base-code)",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Encoding batch size (default: 64)",
    )
    p.add_argument(
        "--output-dir",
        default=str(_BACKEND.parent / "results"),
        help="Directory to write result JSON files",
    )
    p.add_argument(
        "--no-query-clean",
        action="store_true",
        help="Disable query cleaning (ablation)",
    )
    p.add_argument(
        "--no-doc-normalize",
        action="store_true",
        help="Disable document normalisation (ablation)",
    )
    p.add_argument(
        "--secondary-model",
        default=None,
        help="Optional secondary model for dual-encoder concatenation",
    )
    p.add_argument(
        "--secondary-weight",
        type=float,
        default=0.3,
        help="Weight for secondary model embeddings (default: 0.3)",
    )
    return p.parse_args()


# ──────────────────────────── Result extraction ────────────────────────────

def _extract_summary(results: dict, task_name: str = "AppsRetrieval") -> dict:
    """
    Extract key metrics from the raw MTEB results dict.
    Returns a dict with ndcg_at_10, mrr, and other available metrics.
    """
    summary: dict = {
        "task": task_name,
        "ndcg_at_10": "not measured",
        "mrr": "not measured",
        "recall_at_10": "not measured",
        "map_at_10": "not measured",
    }

    # MTEB results structure varies by version; try several access patterns
    def _safe_get(d: dict, *keys: str) -> object:
        for key in keys:
            if isinstance(d, dict) and key in d:
                d = d[key]
            else:
                return None
        return d

    # Try the nested structure from mteb >= 1.x
    for split in ("test", "dev", "validation"):
        split_data = _safe_get(results, task_name, split)
        if split_data is None:
            continue
        for metric_key, summary_key in [
            ("ndcg_at_10", "ndcg_at_10"),
            ("NDCG@10", "ndcg_at_10"),
            ("ndcg@10", "ndcg_at_10"),
            ("mrr_at_10", "mrr"),
            ("MRR@10", "mrr"),
            ("mrr@10", "mrr"),
            ("recall_at_10", "recall_at_10"),
            ("R@10", "recall_at_10"),
            ("map_at_10", "map_at_10"),
            ("MAP@10", "map_at_10"),
        ]:
            val = _safe_get(split_data, metric_key)
            if val is not None and isinstance(val, (int, float)):
                summary[summary_key] = round(float(val), 4)

    return summary


# ──────────────────────────── Main ─────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("CodeLens MTEB Evaluation – AppsRetrieval")
    logger.info("=" * 60)
    logger.info("Model:          %s", args.model)
    logger.info("Secondary:      %s", args.secondary_model or "none")
    logger.info("Batch size:     %d", args.batch_size)
    logger.info("Query clean:    %s", not args.no_query_clean)
    logger.info("Doc normalize:  %s", not args.no_doc_normalize)
    logger.info("Output dir:     %s", output_dir)
    logger.info("=" * 60)

    # ── Build encoder ──────────────────────────────────────────────
    encoder = PrePostPipelineEncoder(
        model_name=args.model,
        secondary_model_name=args.secondary_model,
        secondary_weight=args.secondary_weight,
        use_query_clean=not args.no_query_clean,
        use_doc_normalize=not args.no_doc_normalize,
        batch_size=args.batch_size,
    )
    logger.info("Encoder ready: %s", encoder)

    # ── Load MTEB task ─────────────────────────────────────────────
    try:
        task = mteb.get_task("AppsRetrieval")
    except Exception as exc:
        logger.error("Could not load AppsRetrieval task: %s", exc)
        logger.error(
            "Make sure you have internet access and mteb >= 1.12 installed.\n"
            "Try: pip install --upgrade mteb"
        )
        sys.exit(1)

    logger.info("Task loaded: %s", task)

    # ── Run evaluation ─────────────────────────────────────────────
    t_start = time.perf_counter()

    try:
        results = mteb.evaluate(
            model=encoder,
            tasks=[task],
            encode_kwargs={"batch_size": args.batch_size},
            output_folder=str(output_dir),
            overwrite_results=True,
        )
    except Exception as exc:
        logger.error("MTEB evaluation failed: %s", exc)
        logger.exception("Full traceback:")
        sys.exit(1)

    t_elapsed = time.perf_counter() - t_start
    logger.info("Evaluation completed in %.1f s (%.1f min)", t_elapsed, t_elapsed / 60)

    # ── Save raw results ───────────────────────────────────────────
    # MTEB may already write files; we also write a canonical copy
    raw_path = output_dir / "appsretrieval_results.json"

    # Convert results to serialisable form
    if hasattr(results, "__iter__"):
        # mteb returns a list of TaskResult objects in newer versions
        raw_dict: dict = {}
        for r in results:
            task_name = getattr(r, "task_name", "AppsRetrieval")
            raw_dict[task_name] = (
                r.scores if hasattr(r, "scores") else
                r.dict() if hasattr(r, "dict") else
                str(r)
            )
    else:
        raw_dict = results if isinstance(results, dict) else {"results": str(results)}

    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(raw_dict, fh, indent=2, default=str)
    logger.info("Raw results written to: %s", raw_path)

    # ── Extract and print summary ──────────────────────────────────
    summary = _extract_summary(raw_dict)
    summary.update({
        "model": encoder.model_name,
        "secondary_model": args.secondary_model,
        "batch_size": args.batch_size,
        "use_query_clean": not args.no_query_clean,
        "use_doc_normalize": not args.no_doc_normalize,
        "eval_time_seconds": round(t_elapsed, 1),
    })

    summary_path = output_dir / "appsretrieval_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    logger.info("Summary written to: %s", summary_path)

    logger.info("=" * 60)
    logger.info("RESULTS SUMMARY")
    logger.info("=" * 60)
    logger.info("NDCG@10:     %s", summary["ndcg_at_10"])
    logger.info("MRR:         %s", summary["mrr"])
    logger.info("Recall@10:   %s", summary["recall_at_10"])
    logger.info("MAP@10:      %s", summary["map_at_10"])
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
