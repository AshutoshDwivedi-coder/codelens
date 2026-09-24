"""
rebuild_time.py – Measure full vs incremental rebuild time on sample_repo.

Usage:
    cd codelens/backend
    python benchmarks/rebuild_time.py --repo ../sample_repo
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger("codelens.rebuild_time")

_BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))


def measure_rebuild_times(repo_path: str, output_dir: Path) -> dict:
    from app.services import build_index_for_repo
    from app.config import settings

    results = {}

    # ── Full rebuild ─────────────────────────────────────────────
    logger.info("Measuring full rebuild time…")
    # Clear existing indexes for a clean measurement
    test_sha = "rebuild-test-full"
    snap_dir = settings.indexes_dir / test_sha
    if snap_dir.exists():
        shutil.rmtree(snap_dir)

    t0 = time.perf_counter()
    try:
        manifest = build_index_for_repo(
            repo_path=repo_path,
            commit_sha=test_sha,
            force_full=True,
            progress_callback=lambda m: logger.info("[Full] %s", m),
        )
        full_time = time.perf_counter() - t0
        results["full_rebuild"] = {
            "time_seconds": round(full_time, 2),
            "chunk_count": manifest.get("chunk_count", 0),
            "n_embedded": manifest.get("n_embedded", 0),
            "n_cached": manifest.get("n_cached", 0),
        }
        logger.info("Full rebuild: %.2f s, %d chunks", full_time, manifest.get("chunk_count", 0))
    except Exception as exc:
        logger.error("Full rebuild failed: %s", exc)
        results["full_rebuild"] = {"error": str(exc)}
        full_time = 0.0

    # ── Incremental rebuild (simulate 1 file changed) ─────────────
    logger.info("Measuring incremental rebuild time…")
    test_sha2 = "rebuild-test-incremental"
    snap_dir2 = settings.indexes_dir / test_sha2
    if snap_dir2.exists():
        shutil.rmtree(snap_dir2)

    # Copy the full snapshot as the "previous" one
    snap_dir_full = settings.indexes_dir / test_sha
    if snap_dir_full.exists():
        shutil.copytree(snap_dir_full, snap_dir2)
        # Pretend it was the previous commit (add a manifest)
        import json as _json
        manifest_path = snap_dir2 / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as fh:
                m = _json.load(fh)
            m["commit_sha"] = test_sha2
            with open(manifest_path, "w") as fh:
                _json.dump(m, fh)

    # Now rebuild for a "new commit" with only 1 changed file
    # (simulate by passing a subset of files)
    t0 = time.perf_counter()
    try:
        # In practice we'd use git diff; here we time a forced-small rebuild
        repo = Path(repo_path)
        py_files = list(repo.rglob("*.py"))
        single_file = py_files[:1] if py_files else []

        if single_file:
            from pipeline.chunking import chunk_file, detect_language
            from pipeline.embed import DenseIndex, EmbeddingCache, build_dense_index
            from pipeline.bm25 import BM25Index
            from encoder import PrePostPipelineEncoder

            encoder = PrePostPipelineEncoder(model_name="BAAI/bge-small-en-v1.5", batch_size=8)
            cache_path = settings.indexes_dir / "embed_cache.pkl"
            emb_cache = EmbeddingCache(cache_path)

            chunks = []
            for f in single_file:
                src = f.read_text(encoding="utf-8", errors="replace")
                rel = str(f.relative_to(repo))
                chunks.extend(chunk_file(src, rel))

            test_sha3 = "rebuild-test-incremental-actual"
            snap3 = settings.indexes_dir / test_sha3
            dense, n_emb, n_cached = build_dense_index(chunks, encoder, emb_cache)
            dense.save(snap3)
            bm = BM25Index()
            bm.build(chunks)
            bm.save(snap3)

            inc_time = time.perf_counter() - t0
            results["incremental_rebuild"] = {
                "time_seconds": round(inc_time, 2),
                "files_processed": len(single_file),
                "chunk_count": len(chunks),
                "n_embedded": n_emb,
                "n_cached": n_cached,
                "speedup_vs_full": round(full_time / max(inc_time, 0.001), 1) if full_time > 0 else "N/A",
            }
            logger.info("Incremental rebuild: %.2f s (%.1fx speedup)", inc_time,
                        full_time / max(inc_time, 0.001))
        else:
            results["incremental_rebuild"] = {"note": "No Python files found in repo"}
    except Exception as exc:
        logger.error("Incremental rebuild failed: %s", exc)
        results["incremental_rebuild"] = {"error": str(exc)}

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": str(repo_path),
        **results,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "rebuild_times.json"
    with open(out_path, "w") as fh:
        json.dump(output, fh, indent=2)
    logger.info("Rebuild times written to %s", out_path)
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, help="Path to the sample repository")
    p.add_argument("--output-dir", default=str(_BACKEND.parent / "results"))
    args = p.parse_args()
    measure_rebuild_times(args.repo, Path(args.output_dir))


if __name__ == "__main__":
    main()
