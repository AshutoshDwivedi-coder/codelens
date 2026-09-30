// API client for CodeLens backend

// Leave this empty for local Vite development, where the dev-server proxy
// forwards /api requests to FastAPI. Vercel deployments can override the
// production fallback with VITE_API_BASE_URL at build time.
const DEFAULT_PRODUCTION_API_URL = 'https://codelens-2-v0jy.onrender.com';
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL
  ?? (import.meta.env.PROD ? DEFAULT_PRODUCTION_API_URL : '')
).replace(/\/$/, '');
const apiUrl = (path: string) => `${API_BASE_URL}${path}`;

export interface ScoreBreakdown {
  bm25_rank?: number;
  dense_score?: number;
  fused_score?: number;
  rerank_score?: number;
}

export interface SearchResult {
  chunk_id: string;
  file_path: string;
  commit_id?: string;
  repo_name?: string;
  language: string;
  start_line: number;
  end_line: number;
  score: number;
  content: string;
  code?: string;
  symbol_name?: string;
  symbol_type?: string;
  signature?: string;
  docstring?: string;
  score_breakdown?: ScoreBreakdown;
  bm25_score?: number;
  dense_score?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  timing_ms: number;
  total_candidates: number;
  error?: string | null;
  params?: {
    top_k?: number;
    use_hybrid?: boolean;
    alpha?: number;
    repo_filter?: string;
    commit_id?: string;
  };
}

export interface CommitInfo {
  commit_id: string;
  message: string;
  author: string;
  timestamp: string;
  parent_ids: string[];
}

export interface SnippetHistoryVersion {
  commit_id: string;
  commit_message: string;
  author: string;
  timestamp: string;
  file_path: string;
  content: string;
  start_line: number;
  end_line: number;
}

export interface SnippetHistoryResponse {
  symbol_name: string;
  versions: SnippetHistoryVersion[];
}

export interface HealthResponse {
  status: string;
  version: string;
  indexed_repositories: number;
  total_chunks: number;
  model_name: string;
  bm25_active: boolean;
}

export async function searchCode(params: {
  query: string;
  top_k?: number;
  repo_filter?: string;
  commit_id?: string;
  use_hybrid?: boolean;
  alpha?: number;
}): Promise<SearchResponse> {
  // Map frontend params to the backend SearchRequest schema
  const body: Record<string, unknown> = {
    query: params.query,
    top_k: params.top_k,
    use_hybrid: params.use_hybrid,
  };
  if (params.commit_id) body.commit_id = params.commit_id;
  if (params.repo_filter) body.repo_filter = params.repo_filter;
  if (typeof params.alpha === 'number') body.alpha = params.alpha;

  const res = await fetch(apiUrl('/api/search'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Search request failed');
  }
  const raw = await res.json();
  const rawResults: any[] = raw.results || [];

  const results: SearchResult[] = rawResults.map((r) => {
    const code = r.code || r.content || '';
    const scoreBreak = r.score_breakdown || {};
    const scoreVal =
      scoreBreak.fused_score ?? scoreBreak.dense_score ?? r.score ?? 0.5;

    return {
      chunk_id: r.chunk_id || 'chunk-0',
      file_path: r.file_path || 'file.py',
      commit_id: r.commit_sha || r.commit_id || 'HEAD',
      repo_name: r.repo_name || 'main',
      language: r.language || 'python',
      start_line: r.start_line ?? 1,
      end_line: r.end_line ?? 1,
      score: scoreVal,
      content: code,
      code: code,
      symbol_name: r.symbol_name || '',
      symbol_type: r.chunk_type || r.symbol_type || 'block',
      signature: r.signature || '',
      docstring: r.docstring || '',
      score_breakdown: scoreBreak,
    };
  });

  const timingMs =
    typeof raw.timings?.total_ms === 'number'
      ? raw.timings.total_ms
      : typeof raw.timing_ms === 'number'
      ? raw.timing_ms
      : 0;

  const totalCandidates =
    typeof raw.total_results === 'number'
      ? raw.total_results
      : typeof raw.total_candidates === 'number'
      ? raw.total_candidates
      : results.length;

  return {
    results,
    query: raw.query || params.query,
    timing_ms: timingMs,
    total_candidates: totalCandidates,
    error: typeof raw.error === 'string' ? raw.error : null,
    params: {
      top_k: params.top_k,
      use_hybrid: params.use_hybrid,
      alpha: params.alpha,
      repo_filter: params.repo_filter,
      commit_id: params.commit_id,
    },
  };
}

export async function getVersions(
  repo_name?: string
): Promise<{ commits: CommitInfo[]; current_commit: string }> {
  const url = repo_name
    ? `/api/versions?repo_name=${encodeURIComponent(repo_name)}`
    : '/api/versions';
  const res = await fetch(apiUrl(url));
  if (!res.ok) {
    throw new Error('Failed to fetch commit versions');
  }
  const data = await res.json();
  const versionList: any[] = Array.isArray(data) ? data : data.commits || [];

  const commits: CommitInfo[] = versionList.map((item: any) => ({
    commit_id: item.commit_sha || item.commit_id || 'HEAD',
    message: item.commit_message || item.message || 'Indexed snapshot',
    author: item.author || 'dev',
    timestamp: item.timestamp || '',
    parent_ids: item.parent_ids || [],
  }));

  return {
    commits,
    current_commit: 'HEAD',
  };
}

export async function getSnippetHistory(
  filePath: string,
  commitId?: string
): Promise<SnippetHistoryResponse> {
  const query = commitId ? `?commit_id=${encodeURIComponent(commitId)}` : '';
  // Backend uses a path wildcard route ({file_path:path}), so slashes must
  // NOT be percent-encoded — only the query string should be encoded.
  const res = await fetch(
    apiUrl(`/api/versions/history/${filePath}${query}`)
  );
  if (!res.ok) {
    throw new Error('Failed to fetch snippet evolution history');
  }
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(apiUrl('/api/health'));
  if (!res.ok) throw new Error('Backend health check failed');
  return res.json();
}

export async function startIndexing(
  repoPath?: string
): Promise<{ status: string; job_id: string }> {
  const targetPath = repoPath || '.';
  const res = await fetch(apiUrl('/api/index'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_path: targetPath }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Indexing failed' }));
    throw new Error(err.detail || 'Failed to start indexing');
  }
  return res.json();
}

export interface IndexJobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'done' | 'error';
  progress: string;
  error?: string | null;
  manifest?: {
    repo_name?: string;
    repo_path?: string;
    chunk_count?: number;
  } | null;
}

export async function getIndexingStatus(jobId: string): Promise<IndexJobStatus> {
  const res = await fetch(apiUrl(`/api/index/status?job_id=${encodeURIComponent(jobId)}`));
  if (!res.ok) throw new Error('Failed to check indexing progress');
  return res.json();
}

export interface RepoInfo {
  id: string;
  name: string;
  description: string;
  path: string;
  source: 'indexed' | 'demo' | 'cloned';
  chunk_count: number;
}

export async function getRepos(): Promise<{ repos: RepoInfo[] }> {
  const res = await fetch(apiUrl('/api/repos'));
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to fetch repositories' }));
    throw new Error(err.detail || 'Failed to fetch repositories');
  }
  return res.json();
}

export interface ReadmeAnalysis {
  has_readme: boolean;
  filename?: string | null;
  readme_path?: string | null;
  repo_name: string;
  title: string;
  summary: string;
  features: string[];
  key_modules: string[];
  suggested_questions: string[];
  categories: Record<string, string[]>;
}

export async function analyzeReadme(
  repoPath?: string
): Promise<ReadmeAnalysis> {
  const query = repoPath && repoPath !== 'all' ? `?repo_path=${encodeURIComponent(repoPath)}` : '';
  const res = await fetch(apiUrl(`/api/readme/analyze${query}`));
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to analyze repository README' }));
    throw new Error(err.detail || 'Failed to analyze repository README');
  }
  return res.json();
}
export interface RepositoryReadme {
  repo_name: string;
  filename: string;
  content: string;
}

export async function getRepositoryReadme(repoPath?: string): Promise<RepositoryReadme> {
  const query = repoPath ? `?repo_path=${encodeURIComponent(repoPath)}` : '';
  const res = await fetch(apiUrl(`/api/readme/content${query}`));
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Could not open repository README' }));
    throw new Error(err.detail || 'Could not open repository README');
  }
  return res.json();
}
