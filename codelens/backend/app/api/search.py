"""
search.py – Core search API router for CodeLens.

GET /api/search?q=&version=&lang=&type=&rerank=&hybrid=&clean=
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("codelens.api.search")

router = APIRouter()


# ──────────────────────────── Response models ──────────────────────────────


class ScoreBreakdown(BaseModel):
    bm25_rank: Optional[int] = None
    dense_score: Optional[float] = None
    fused_score: Optional[float] = None
    rerank_score: Optional[float] = None


class TimingBreakdown(BaseModel):
    cache_ms: Optional[float] = None
    query_clean_ms: Optional[float] = None
    embed_ms: Optional[float] = None
    bm25_ms: Optional[float] = None
    dense_ms: Optional[float] = None
    fusion_ms: Optional[float] = None
    rerank_ms: Optional[float] = None
    total_ms: float


class OtherVersion(BaseModel):
    commit_sha: str
    score: float
    chunk_id: str


class SearchResult(BaseModel):
    chunk_id: str
    lineage_id: str
    file_path: str
    symbol_name: str
    signature: str
    docstring: str
    language: str
    chunk_type: str
    start_line: int
    end_line: int
    code: str
    score_breakdown: ScoreBreakdown
    other_versions: list[OtherVersion] = []
    tags: dict = {}
    repo_name: str = ""


class SearchResponse(BaseModel):
    query: str
    cleaned_query: str
    query_type: str
    version: str
    total_results: int
    results: list[SearchResult]
    timings: TimingBreakdown
    config_used: dict
    error: Optional[str] = None


class SearchRequest(BaseModel):
    query: Optional[str] = None
    q: Optional[str] = None
    version: str = "latest"
    commit_id: Optional[str] = None
    lang: Optional[str] = None
    type: Optional[str] = None
    rerank: Optional[bool] = None
    use_hybrid: Optional[bool] = None
    hybrid: Optional[bool] = None
    clean: Optional[bool] = None
    top_k: int = 10
    repo_filter: Optional[str] = None
    alpha: Optional[float] = None


@router.post("/search", response_model=SearchResponse)
async def post_search(body: SearchRequest):
    search_q = body.query or body.q
    if not search_q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' or 'query' is required")
    target_ver = body.commit_id or body.version or "latest"
    use_h = body.use_hybrid if body.use_hybrid is not None else body.hybrid
    return await search(
        q=search_q,
        version=target_ver,
        lang=body.lang,
        type=body.type,
        rerank=body.rerank,
        hybrid=use_h,
        clean=body.clean,
        top_k=body.top_k,
        repo_filter=body.repo_filter,
    )


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    version: str = Query("latest", description="Commit SHA or tag"),
    lang: Optional[str] = Query(None, description="Language filter (python, javascript, …)"),
    type: Optional[str] = Query(None, description="Chunk type filter (function, class, block)"),
    rerank: Optional[bool] = Query(None, description="Override rerank toggle"),
    hybrid: Optional[bool] = Query(None, description="Override hybrid (BM25+dense) toggle"),
    clean: Optional[bool] = Query(None, description="Override query cleaning toggle"),
    top_k: int = Query(10, ge=1, le=50, description="Number of results to return"),
    repo_filter: Optional[str] = Query(None, description="Comma-separated repo names to search"),
):
    """
    Main code search endpoint.

    Returns ranked code chunks with per-result score breakdowns and
    per-stage timing information.
    """
    from app.services import get_search_service

    t_total_start = time.perf_counter()
    timings: dict = {}

    svc = get_search_service()
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="Search service not initialised. Index a repository first via POST /api/index",
        )

    # Override config from query params
    overrides: dict = {}
    if rerank is not None:
        overrides["use_rerank"] = rerank
    if hybrid is not None:
        overrides["use_hybrid"] = hybrid
    if clean is not None:
        overrides["use_query_clean"] = clean

    try:
        result = await svc.search(
            query=q,
            version=version,
            lang_filter=lang,
            type_filter=type,
            repo_filter=repo_filter,
            top_k=top_k,
            config_overrides=overrides,
            timings=timings,
        )
    except Exception as exc:
        logger.exception("Search failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Search error: {exc}")

    timings["total_ms"] = round((time.perf_counter() - t_total_start) * 1000, 1)

    return SearchResponse(
        query=q,
        cleaned_query=result.get("cleaned_query", q),
        query_type=result.get("query_type", "general"),
        version=result.get("version", version),
        total_results=result.get("total_results", 0),
        results=[
            SearchResult(
                chunk_id=r["chunk_id"],
                lineage_id=r.get("lineage_id", ""),
                file_path=r.get("file_path", ""),
                symbol_name=r.get("symbol_name", ""),
                signature=r.get("signature", ""),
                docstring=r.get("docstring", ""),
                language=r.get("language", ""),
                chunk_type=r.get("chunk_type", "block"),
                start_line=r.get("start_line", 1),
                end_line=r.get("end_line", 1),
                code=r.get("code", ""),
                score_breakdown=ScoreBreakdown(
                    bm25_rank=r.get("bm25_rank"),
                    dense_score=r.get("_orig_scores", {}).get("dense"),
                    fused_score=r.get("fused_score"),
                    rerank_score=r.get("rerank_score"),
                ),
                other_versions=[
                    OtherVersion(**v) for v in r.get("other_versions", [])
                ],
                tags=r.get("tags", {}),
                repo_name=r.get("repo_name") or (r.get("tags") or {}).get("repo_name") or "",
            )
            for r in result.get("results", [])
        ],
        timings=TimingBreakdown(**{k: v for k, v in timings.items() if k in TimingBreakdown.model_fields}),
        config_used=result.get("config_used", {}),
        error=result.get("error"),
    )
