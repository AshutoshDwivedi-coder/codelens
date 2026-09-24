"""
indexer_worker.py – Standalone background indexer worker.

Can be run as a separate process so indexing never blocks serving.
Uses a simple file-based job queue (watches a directory for .job files).

Usage:
    python indexer_worker.py --watch-dir /tmp/codelens-jobs
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
logger = logging.getLogger("codelens.indexer_worker")

_BACKEND = Path(__file__).parent
sys.path.insert(0, str(_BACKEND))


def process_job(job_path: Path) -> None:
    """Process a single .job file."""
    try:
        with open(job_path) as fh:
            job = json.load(fh)
    except Exception as exc:
        logger.error("Could not read job file %s: %s", job_path, exc)
        return

    logger.info("Processing job: %s", job)
    from app.services import build_index_for_repo

    try:
        manifest = build_index_for_repo(
            repo_path=job.get("repo_path", "."),
            commit_sha=job.get("commit_sha"),
            force_full=job.get("force_full", False),
            progress_callback=lambda msg: logger.info("[Job] %s", msg),
        )
        logger.info("Job complete: %s", manifest)
        # Write result
        result_path = job_path.with_suffix(".result.json")
        with open(result_path, "w") as fh:
            json.dump({"status": "done", "manifest": manifest}, fh)
    except Exception as exc:
        logger.exception("Job failed: %s", exc)
        result_path = job_path.with_suffix(".result.json")
        with open(result_path, "w") as fh:
            json.dump({"status": "error", "error": str(exc)}, fh)
    finally:
        job_path.unlink(missing_ok=True)


def watch_loop(watch_dir: Path, poll_interval: float = 2.0) -> None:
    watch_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Indexer worker watching: %s (poll=%.1fs)", watch_dir, poll_interval)
    while True:
        for job_file in sorted(watch_dir.glob("*.job")):
            process_job(job_file)
        time.sleep(poll_interval)


def main() -> None:
    p = argparse.ArgumentParser(description="CodeLens background indexer worker")
    p.add_argument("--watch-dir", default="/tmp/codelens-jobs", help="Directory to watch for .job files")
    p.add_argument("--poll-interval", type=float, default=2.0)
    # One-shot mode: index a single repo and exit
    p.add_argument("--repo", help="Repo path for one-shot indexing")
    p.add_argument("--commit", help="Commit SHA (default: HEAD)")
    p.add_argument("--force-full", action="store_true")
    args = p.parse_args()

    if args.repo:
        # One-shot
        from app.services import build_index_for_repo
        manifest = build_index_for_repo(
            repo_path=args.repo,
            commit_sha=args.commit,
            force_full=args.force_full,
            progress_callback=lambda msg: logger.info("[Indexer] %s", msg),
        )
        logger.info("Done: %s", manifest)
    else:
        watch_loop(Path(args.watch_dir), poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
