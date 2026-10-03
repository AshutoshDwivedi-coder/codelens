"""
index_api.py – Index management API endpoints.

POST /api/index          – trigger async indexing job
GET  /api/index/status   – job status
GET  /api/versions       – list indexed commits
GET  /api/lineage/{id}   – snippet history
GET  /api/snippet/{id}   – get a specific chunk
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path as FPath, Query
from pydantic import BaseModel

logger = logging.getLogger("codelens.api.index")

router = APIRouter()

# ──────────────────────────── Job state store (disk-backed) ──────────────────

def _jobs_file() -> Path:
    """Return the path to the on-disk jobs JSON, creating its directory if needed."""
    try:
        from app.config import settings
        p = settings.indexes_dir / "_jobs.json"
    except Exception:
        p = Path("/tmp/_codelens_jobs.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_jobs() -> dict:
    p = _jobs_file()
    if p.exists():
        try:
            data = json.loads(p.read_text())
            modified = False
            for jid, j in data.items():
                if j.get("status") in ("pending", "running"):
                    j["status"] = "error"
                    j["progress"] = "Interrupted"
                    j["error"] = "Indexing was interrupted by server reboot or memory limit. Please retry."
                    modified = True
            if modified:
                try:
                    p.write_text(json.dumps(data))
                except Exception:
                    pass
            return data
        except Exception:
            pass
    return {}


def _save_jobs(jobs: dict) -> None:
    try:
        _jobs_file().write_text(json.dumps(jobs))
    except Exception as exc:
        logger.warning("Could not persist jobs: %s", exc)


# In-memory mirror (populated lazily from disk on first access)
_jobs: dict[str, dict] = {}
_jobs_loaded = False


def _get_jobs() -> dict:
    global _jobs, _jobs_loaded
    if not _jobs_loaded:
        _jobs = _load_jobs()
        _jobs_loaded = True
    return _jobs


class IndexRequest(BaseModel):
    repo_path: str
    commit_sha: Optional[str] = None  # None = use HEAD
    force_full: bool = False          # ignore incremental, rebuild everything


class IndexStatusResponse(BaseModel):
    job_id: str
    status: str   # pending | running | done | error
    progress: str
    error: Optional[str] = None
    manifest: Optional[dict] = None
    elapsed_seconds: Optional[float] = None


class VersionInfo(BaseModel):
    commit_sha: str
    tag: str
    commit_message: str
    timestamp: str
    chunk_count: int
    model_name: str
    build_time_seconds: float


# ──────────────────────────── Endpoints ───────────────────────────────────


@router.post("/index", status_code=202)
async def trigger_index(
    req: IndexRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger an async indexing job for a repository commit."""
    job_id = str(uuid.uuid4())[:8]
    jobs = _get_jobs()
    jobs[job_id] = {
        "status": "pending",
        "progress": "Queued",
        "started_at": time.time(),
        "error": None,
        "manifest": None,
    }
    _save_jobs(jobs)
    background_tasks.add_task(_run_index_job, job_id, req)
    return {"job_id": job_id, "status": "pending"}


async def _run_index_job(job_id: str, req: IndexRequest) -> None:
    """Background indexing task."""
    from app.services import build_index_for_repo

    jobs = _get_jobs()
    jobs[job_id]["status"] = "running"
    jobs[job_id]["progress"] = "Starting indexer…"
    _save_jobs(jobs)
    t_start = time.time()

    try:
        from app.readme_analyzer import is_remote_git_url, clone_git_repo
        repo_path = req.repo_path
        if is_remote_git_url(repo_path):
            ok, message, local_path = await asyncio.get_event_loop().run_in_executor(
                None, lambda: clone_git_repo(repo_path)
            )
            if not ok:
                raise RuntimeError(message)
            repo_path = str(local_path)
            _update_progress(job_id, f"Cloned repository; indexing {local_path.name}…")
        manifest = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: build_index_for_repo(
                repo_path=repo_path,
                commit_sha=req.commit_sha,
                force_full=req.force_full,
                progress_callback=lambda msg: _update_progress(job_id, msg),
            ),
        )
        jobs = _get_jobs()
        jobs[job_id]["status"] = "done"
        jobs[job_id]["progress"] = "Index complete"
        jobs[job_id]["manifest"] = manifest
        _save_jobs(jobs)
    except Exception as exc:
        logger.exception("Indexing job %s failed: %s", job_id, exc)
        jobs = _get_jobs()
        jobs[job_id]["status"] = "error"
        jobs[job_id]["progress"] = "Failed"
        jobs[job_id]["error"] = str(exc)
        _save_jobs(jobs)

    jobs = _get_jobs()
    jobs[job_id]["elapsed_seconds"] = round(time.time() - t_start, 1)
    _save_jobs(jobs)


def _update_progress(job_id: str, msg: str) -> None:
    jobs = _get_jobs()
    if job_id in jobs:
        jobs[job_id]["progress"] = msg
        _save_jobs(jobs)
        logger.info("[Job %s] %s", job_id, msg)


@router.get("/index/status", response_model=IndexStatusResponse)
async def index_status(job_id: str = Query(..., description="Job ID from POST /api/index")):
    """Get the status of an indexing job."""
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return IndexStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        error=job.get("error"),
        manifest=job.get("manifest"),
        elapsed_seconds=job.get("elapsed_seconds"),
    )


@router.get("/versions", response_model=list[VersionInfo])
async def list_versions():
    """List all indexed commits/tags."""
    from pipeline.versioning import get_version_manager

    vm = get_version_manager()
    snapshots = vm.list_snapshots()
    return [
        VersionInfo(
            commit_sha=s.get("commit_sha", ""),
            tag=s.get("tag", ""),
            commit_message=s.get("commit_message", ""),
            timestamp=s.get("timestamp", ""),
            chunk_count=s.get("chunk_count", 0),
            model_name=s.get("model_name", ""),
            build_time_seconds=s.get("build_time_seconds", 0.0),
        )
        for s in snapshots
    ]


@router.get("/lineage/{lineage_id}")
async def get_lineage(lineage_id: str = FPath(..., description="Lineage ID")):
    """Get all versions of a snippet across indexed commits."""
    from app.config import settings
    from pipeline.lineage import get_lineage_history, diff_versions

    history = get_lineage_history(lineage_id, settings.indexes_dir)
    if not history:
        raise HTTPException(status_code=404, detail=f"Lineage {lineage_id!r} not found")

    # Compute diffs between adjacent versions
    diffs = []
    for i in range(len(history) - 1):
        newer = history[i]
        older = history[i + 1]
        diff_lines = diff_versions(
            older["code"], newer["code"],
            label_a=older["commit_sha"][:7],
            label_b=newer["commit_sha"][:7],
        )
        diffs.append({
            "from_sha": older["commit_sha"],
            "to_sha": newer["commit_sha"],
            "lines": diff_lines,
        })

    return {"lineage_id": lineage_id, "history": history, "diffs": diffs}


@router.get("/snippet/{chunk_id}")
async def get_snippet(chunk_id: str = FPath(..., description="Chunk ID")):
    """Retrieve a specific code chunk by ID."""
    from app.services import get_search_service

    svc = get_search_service()
    if svc is None:
        raise HTTPException(status_code=503, detail="Search service not initialised")

    chunk = svc.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id!r} not found")
    return chunk


@router.get("/eval")
async def get_eval():
    """Return the latest real evaluation results and ablation table."""
    import json
    from pathlib import Path
    from app.config import settings

    results_dir = settings.results_dir
    output: dict = {
        "note": "All metrics come from real runs. 'not measured' means the evaluation has not been run yet.",
        "appsretrieval": None,
        "ablation": None,
        "rebuild_times": None,
    }

    summary_path = results_dir / "appsretrieval_summary.json"
    if summary_path.exists():
        with open(summary_path) as fh:
            output["appsretrieval"] = json.load(fh)

    ablation_path = results_dir / "ablation_results.json"
    if ablation_path.exists():
        with open(ablation_path) as fh:
            output["ablation"] = json.load(fh)

    rebuild_path = results_dir / "rebuild_times.json"
    if rebuild_path.exists():
        with open(rebuild_path) as fh:
            output["rebuild_times"] = json.load(fh)

    return output


@router.get("/lineage/history/by-path")
async def get_lineage_by_path(
    file_path: str = Query(..., description="Relative file path"),
    commit_id: Optional[str] = Query(None, description="Optional commit SHA"),
):
    """Find lineage history for a file path across snapshots."""
    import hashlib
    from app.config import settings
    from pipeline.lineage import get_lineage_history

    indexes_dir = settings.indexes_dir
    history = []
    if indexes_dir.exists():
        for snap_dir in sorted(indexes_dir.iterdir(), reverse=True):
            if not snap_dir.is_dir():
                continue
            chunks_path = snap_dir / "chunks.json"
            manifest_path = snap_dir / "manifest.json"
            if not chunks_path.exists():
                continue
            try:
                import json
                with open(chunks_path) as fh:
                    chunks = json.load(fh)
                manifest = {}
                if manifest_path.exists():
                    with open(manifest_path) as fh:
                        manifest = json.load(fh)
                for chunk in chunks:
                    if chunk.get("file_path") == file_path:
                        history.append({
                            "commit_id": manifest.get("commit_sha", snap_dir.name),
                            "commit_message": manifest.get("commit_message", "Update"),
                            "author": "dev",
                            "timestamp": manifest.get("timestamp", ""),
                            "file_path": file_path,
                            "content": chunk.get("code", ""),
                            "start_line": chunk.get("start_line", 1),
                            "end_line": chunk.get("end_line", 1),
                        })
                        break
            except Exception:
                pass
    return {"symbol_name": file_path, "versions": history}


@router.get("/versions/history/{file_path:path}")
async def get_history_by_path_route(
    file_path: str,
    commit_id: Optional[str] = Query(None),
):
    """Compatibility route for snippet evolution history by file path."""
    return await get_lineage_by_path(file_path=file_path, commit_id=commit_id)


@router.get("/repos")
async def list_repos():
    """
    List repositories with completed indexes only.
    """
    from app.config import settings
    import json

    repos = []
    seen_names: set[str] = set()

    indexes_dir = settings.indexes_dir
    if indexes_dir.exists():
        indexed_entries = []
        for snap_dir in indexes_dir.iterdir():
            if not snap_dir.is_dir():
                continue
            manifest_path = snap_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                with open(manifest_path) as fh:
                    manifest = json.load(fh)
                repo_path = manifest.get("repo_path", "")
                repo_name = manifest.get("repo_name") or (
                    Path(repo_path).name if repo_path else snap_dir.name
                )
                indexed_entries.append((
                    manifest.get("timestamp", ""),
                    repo_name,
                    repo_path or str(snap_dir),
                    manifest.get("chunk_count", 0),
                ))
            except Exception:
                pass
        for _, repo_name, repo_path, chunk_count in sorted(indexed_entries, reverse=True):
            if repo_name and repo_name not in seen_names:
                seen_names.add(repo_name)
                repos.append({
                    "id": repo_name,
                    "name": repo_name,
                    "description": f"Indexed codebase · {chunk_count} code chunks",
                    "path": repo_path,
                    "source": "indexed",
                    "chunk_count": chunk_count,
                })

    return {"repos": repos}


@router.get("/health")
async def health():
    """Health check endpoint with full system metrics."""
    from app.services import get_search_service
    from app.cache import get_cache
    from pipeline.versioning import get_version_manager

    svc = get_search_service()
    cache = get_cache()
    vm = get_version_manager()
    snapshots = vm.list_snapshots()
    latest_by_repo: dict = {}
    for snap in snapshots:
        key = snap.get("repo_name") or snap.get("commit_sha")
        if key and key not in latest_by_repo:
            latest_by_repo[key] = snap
    total_chunks = sum(s.get("chunk_count", 0) for s in latest_by_repo.values())

    return {
        "status": "ok",
        "version": "1.0.0",
        "indexed_repositories": len(latest_by_repo),
        "total_chunks": total_chunks,
        "model_name": "bge-small-en-v1.5",
        "bm25_active": True,
        "index_loaded": svc is not None,
        "cache_backend": cache.backend_name if cache else "none",
        "cache_stats": cache.stats() if cache else {},
    }
