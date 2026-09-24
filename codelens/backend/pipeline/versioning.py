"""
versioning.py – Per-commit index snapshots and incremental rebuild.

Manages:
  - Creating index snapshots at indexes/<commit_sha>/
  - Writing a manifest (commit, timestamp, chunk count, model, build time)
  - Listing available snapshots
  - Detecting which files changed between two commits (git diff)
  - Incremental rebuild: only re-chunk/re-embed changed files
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("codelens.versioning")


MANIFEST_FILE = "manifest.json"


def _run_git(args: list[str], cwd: str) -> tuple[str, str, int]:
    """Run a git command and return (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "git command timed out", 1
    except FileNotFoundError:
        return "", "git not found in PATH", 1


class VersionManager:
    """
    Manages the indexes directory and per-commit snapshots.

    indexes/
      <commit_sha>/
        manifest.json
        faiss.index  (or vectors.npy)
        chunks.json
        bm25_index.pkl
        bm25_chunks.json
        index_meta.json
        embed_cache.pkl
    """

    def __init__(self, indexes_dir: Path) -> None:
        self.indexes_dir = Path(indexes_dir)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────── Snapshot paths ──────────────────

    def snapshot_dir(self, commit_sha: str) -> Path:
        return self.indexes_dir / commit_sha

    def has_snapshot(self, commit_sha: str) -> bool:
        manifest = self.snapshot_dir(commit_sha) / MANIFEST_FILE
        return manifest.exists()

    def list_snapshots(self) -> list[dict]:
        """Return list of manifest dicts for all existing snapshots."""
        snapshots = []
        for d in sorted(self.indexes_dir.iterdir()):
            if not d.is_dir():
                continue
            manifest_path = d / MANIFEST_FILE
            if manifest_path.exists():
                try:
                    with open(manifest_path) as fh:
                        snapshots.append(json.load(fh))
                except Exception as exc:
                    logger.warning("Could not read manifest at %s: %s", d, exc)
        return sorted(snapshots, key=lambda m: m.get("timestamp", ""), reverse=True)

    # ──────────────────────────── Manifest ────────────────────────

    def write_manifest(
        self,
        commit_sha: str,
        chunk_count: int,
        model_name: str,
        build_time_seconds: float,
        n_embedded: int,
        n_cached: int,
        commit_message: str = "",
        tag: str = "",
    ) -> dict:
        manifest = {
            "commit_sha": commit_sha,
            "tag": tag,
            "commit_message": commit_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chunk_count": chunk_count,
            "model_name": model_name,
            "build_time_seconds": round(build_time_seconds, 2),
            "n_embedded": n_embedded,
            "n_cached": n_cached,
        }
        snap_dir = self.snapshot_dir(commit_sha)
        snap_dir.mkdir(parents=True, exist_ok=True)
        with open(snap_dir / MANIFEST_FILE, "w") as fh:
            json.dump(manifest, fh, indent=2)
        logger.info("Manifest written: %s", snap_dir / MANIFEST_FILE)
        return manifest

    def read_manifest(self, commit_sha: str) -> Optional[dict]:
        path = self.snapshot_dir(commit_sha) / MANIFEST_FILE
        if not path.exists():
            return None
        with open(path) as fh:
            return json.load(fh)

    # ──────────────────────────── Git helpers ─────────────────────

    def get_changed_files(self, repo_dir: str, from_sha: str, to_sha: str) -> list[str]:
        """
        Return list of files changed between *from_sha* and *to_sha*.
        Paths are relative to *repo_dir*.
        """
        stdout, stderr, rc = _run_git(
            ["diff", "--name-only", from_sha, to_sha],
            cwd=repo_dir,
        )
        if rc != 0:
            logger.warning("git diff failed: %s", stderr)
            return []
        return [f.strip() for f in stdout.splitlines() if f.strip()]

    def get_current_commit(self, repo_dir: str) -> str:
        """Return HEAD commit SHA for *repo_dir*."""
        stdout, stderr, rc = _run_git(["rev-parse", "HEAD"], cwd=repo_dir)
        if rc != 0:
            logger.warning("Could not get HEAD: %s", stderr)
            return "unknown"
        return stdout.strip()

    def get_commit_message(self, repo_dir: str, sha: str) -> str:
        stdout, _, _ = _run_git(["log", "-1", "--pretty=%s", sha], cwd=repo_dir)
        return stdout.strip()

    def get_repo_tags(self, repo_dir: str) -> dict[str, str]:
        """Return {tag_name: commit_sha}."""
        stdout, _, rc = _run_git(["tag", "-l", "--format=%(refname:short) %(objectname:short)"], cwd=repo_dir)
        if rc != 0:
            return {}
        tags = {}
        for line in stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                tags[parts[0]] = parts[1]
        return tags


# ──────────────────────────── Singleton factory ────────────────────────────

_version_manager: Optional[VersionManager] = None


def get_version_manager(indexes_dir: Optional[Path] = None) -> VersionManager:
    global _version_manager
    if _version_manager is None:
        if indexes_dir is None:
            from app.config import settings
            indexes_dir = settings.indexes_dir
        _version_manager = VersionManager(indexes_dir)
    return _version_manager
