"""
readme_api.py – API endpoints to read, analyze repository README files,
and generate suggested questions to be asked to the codebase.

GET  /api/readme/analyze?repo_path=...
POST /api/readme/analyze {"repo_path": "..."}
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.readme_analyzer import analyze_readme, resolve_repo_dir, find_readme_file

logger = logging.getLogger("codelens.api.readme")

router = APIRouter()


class ReadmeAnalyzeRequest(BaseModel):
    repo_path: Optional[str] = None


class ReadmeAnalyzeResponse(BaseModel):
    has_readme: bool
    filename: Optional[str] = None
    readme_path: Optional[str] = None
    repo_name: str
    title: str
    summary: str
    features: List[str] = []
    key_modules: List[str] = []
    suggested_questions: List[str] = []
    categories: Dict[str, List[str]] = {}


@router.get("/readme/analyze", response_model=ReadmeAnalyzeResponse)
async def get_readme_analyze(
    repo_path: Optional[str] = Query(None, description="Repository path or alias (e.g. 'all', 'codelens-backend', 'codelens-frontend', or folder path)")
):
    """
    Read and analyze the README file of the selected repository,
    extracting summary, features, modules, and generating questions.
    """
    return analyze_readme(repo_path)


@router.post("/readme/analyze", response_model=ReadmeAnalyzeResponse)
async def post_readme_analyze(body: ReadmeAnalyzeRequest):
    """
    POST route for repository README analysis.
    """
    return analyze_readme(body.repo_path)


@router.get("/readme/content")
async def get_readme_content(
    repo_path: Optional[str] = Query(None, description="Repository path or alias"),
):
    """Return the selected repository's README text for the in-app reader."""
    resolved_dir, remote_content, repo_name = resolve_repo_dir(repo_path)
    if remote_content:
        return {"repo_name": repo_name or resolved_dir.name, "filename": "README.md", "content": remote_content}

    readme_file = find_readme_file(resolved_dir)
    if readme_file is None:
        raise HTTPException(status_code=404, detail=f"No README found for {repo_name or resolved_dir.name}")
    try:
        content = readme_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not read {readme_file.name}") from exc
    return {"repo_name": repo_name or resolved_dir.name, "filename": readme_file.name, "content": content}
