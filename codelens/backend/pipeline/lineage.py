"""
lineage.py – Snippet lineage tracking across git versions.

A lineage_id = sha256(file_path + symbol_name) is stable across commits
as long as the symbol lives in the same file.

This module provides:
  - group_by_lineage: collapse a result list, keeping best per lineage
  - get_lineage_history: all snapshots of a lineage_id across indexed commits
  - diff_versions: side-by-side diff between two chunk versions
"""
from __future__ import annotations

import difflib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("codelens.lineage")


def group_by_lineage(
    results: list[tuple[float, dict]],
    version_collapse: bool = True,
) -> list[tuple[float, dict]]:
    """
    Collapse results by lineage_id: keep the highest-scoring version of each
    snippet; attach the list of other versions as 'other_versions'.

    Parameters
    ----------
    results:          (score, chunk_dict) list, sorted descending
    version_collapse: if False, return results as-is

    Returns
    -------
    Collapsed list with at most one entry per lineage_id.
    """
    if not version_collapse:
        return results

    seen: dict[str, int] = {}   # lineage_id → index in output
    output: list[tuple[float, dict]] = []

    for score, chunk in results:
        lid = chunk.get("lineage_id", "")
        if not lid:
            output.append((score, chunk))
            continue

        if lid in seen:
            # Add to other_versions of the best entry
            idx = seen[lid]
            best_chunk = output[idx][1]
            if "other_versions" not in best_chunk:
                best_chunk["other_versions"] = []
            best_chunk["other_versions"].append({
                "commit_sha": chunk.get("commit_sha", ""),
                "score": score,
                "chunk_id": chunk.get("chunk_id", ""),
            })
        else:
            chunk = dict(chunk)
            chunk["other_versions"] = []
            seen[lid] = len(output)
            output.append((score, chunk))

    return output


def get_lineage_history(
    lineage_id: str,
    indexes_dir: Path,
) -> list[dict]:
    """
    Return all indexed versions of the snippet with *lineage_id*, ordered by
    commit timestamp (newest first).

    Each entry:
      commit_sha, timestamp, chunk_id, code, signature, docstring,
      start_line, end_line, commit_message
    """
    history: list[dict] = []

    for snap_dir in sorted(indexes_dir.iterdir(), reverse=True):
        if not snap_dir.is_dir():
            continue
        chunks_path = snap_dir / "chunks.json"
        manifest_path = snap_dir / "manifest.json"
        if not chunks_path.exists():
            continue

        try:
            with open(chunks_path) as fh:
                chunks = json.load(fh)
            manifest = {}
            if manifest_path.exists():
                with open(manifest_path) as fh:
                    manifest = json.load(fh)
        except Exception as exc:
            logger.warning("Error reading snapshot %s: %s", snap_dir.name, exc)
            continue

        for chunk in chunks:
            if chunk.get("lineage_id") == lineage_id:
                history.append({
                    "commit_sha": manifest.get("commit_sha", snap_dir.name),
                    "timestamp": manifest.get("timestamp", ""),
                    "commit_message": manifest.get("commit_message", ""),
                    "chunk_id": chunk.get("chunk_id", ""),
                    "code": chunk.get("code", ""),
                    "signature": chunk.get("signature", ""),
                    "docstring": chunk.get("docstring", ""),
                    "start_line": chunk.get("start_line", 1),
                    "end_line": chunk.get("end_line", 1),
                    "file_path": chunk.get("file_path", ""),
                    "symbol_name": chunk.get("symbol_name", ""),
                })
                break  # only one per snapshot

    return history


def diff_versions(code_a: str, code_b: str, label_a: str = "v1", label_b: str = "v2") -> list[dict]:
    """
    Compute a unified diff between two code strings.

    Returns a list of line-level diff objects:
      {"type": "context"|"add"|"remove", "line": str, "line_no_a": int|None, "line_no_b": int|None}
    """
    lines_a = code_a.splitlines(keepends=True)
    lines_b = code_b.splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        lines_a, lines_b,
        fromfile=label_a, tofile=label_b,
        lineterm="",
    ))

    result: list[dict] = []
    ln_a = 0
    ln_b = 0
    for line in diff:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            # Parse hunk header @@ -a,c +b,d @@
            import re
            m = re.search(r"-(\d+).*\+(\d+)", line)
            if m:
                ln_a = int(m.group(1)) - 1
                ln_b = int(m.group(2)) - 1
            continue

        if line.startswith("+"):
            ln_b += 1
            result.append({"type": "add", "line": line[1:].rstrip("\n"), "line_no_a": None, "line_no_b": ln_b})
        elif line.startswith("-"):
            ln_a += 1
            result.append({"type": "remove", "line": line[1:].rstrip("\n"), "line_no_a": ln_a, "line_no_b": None})
        else:
            ln_a += 1
            ln_b += 1
            result.append({"type": "context", "line": line[1:].rstrip("\n"), "line_no_a": ln_a, "line_no_b": ln_b})

    return result
