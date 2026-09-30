# CodeLens

CodeLens is a local-first code search tool for finding and inspecting relevant source code in one or more repositories. Search with a plain-language question, a symbol name, or exact technical terms; then review the ranked code snippets, file locations, and match details in the web interface.

The project includes a React + TypeScript frontend and a FastAPI backend. Repositories are indexed into versioned snapshots that contain code chunks and lexical and vector search indexes. The retrieval pipeline is CPU-capable and can use Redis when available, with an in-memory cache fallback.

## Features

### Search and retrieval

- **Natural-language and keyword search:** Ask questions about behavior or search for exact identifiers, filenames, and terms.
- **Hybrid retrieval:** Combines BM25 lexical results with dense vector similarity using Reciprocal Rank Fusion (RRF). The configured reranker can refine results when the candidates do not already appear high-confidence. Hybrid and conceptual-only modes are exposed in the frontend.
- **Repository and version scope:** Search across indexed repositories or select one or more repositories, and choose the current `HEAD` snapshot or an indexed commit.
- **Ranked, inspectable results:** Each match includes a file path, line range, symbol metadata where available, source code, and score details. Choose a result to inspect its snippet, copy the code, or open its version history.
- **Search controls and telemetry:** Set the result limit and view retrieval strategy, result count, total candidates, and search timing.
- **Query suggestions:** The interface reads project README information to show a summary, key modules, and suggested questions. Example questions are available when the README has no suggestions.

### Repository indexing

- **Local and remote repositories:** Index a local folder or provide a GitHub repository reference through the repository controls.
- **Background indexing jobs:** Index requests run asynchronously and report progress and completion status through the API and frontend.
- **AST-aware code chunks:** Tree-sitter extracts functions, methods, classes, signatures, and docstrings for supported languages. If a grammar or parser is unavailable, indexing falls back to line-based chunks.
- **Incremental and versioned snapshots:** Index metadata records the source repository and commit so search can target indexed versions and code history can be inspected.
- **Dense and lexical indexes:** Embeddings and BM25 data are built for the chunks and saved with the index snapshot. The project uses FAISS for dense retrieval.

The current extension map includes Python, JavaScript/JSX, TypeScript/TSX, Go, Java, Rust, C/C++, Ruby, and PHP. Indexing skips common generated and environment directories such as `.git`, `node_modules`, `.venv`, and `venv`.

### History, project context, and operations

- **Code evolution:** Inspect a file's available indexed versions and compare the snippet across snapshots.
- **README insights:** Analyze a repository README to show its summary, documented features, key files, and suggested search questions. README content can also be retrieved through the API.
- **Repository picker:** Discover indexed, demo, and cloned repositories; select search scope or add a local path / GitHub repository.
- **Status and cache information:** The health endpoint reports index and cache status, repository and chunk counts, and the active embedding model.
- **Developer guide:** The frontend includes search examples and explanations of concepts such as BM25, dense embeddings, RRF, and AST chunking.

## How search works

1. CodeLens resolves the requested repository and snapshot.
2. The query is cleaned and classified when query cleaning is enabled.
3. The query is embedded and searched against the dense index; BM25 performs lexical retrieval when enabled.
4. Hybrid results are combined with RRF. The configured cross-encoder can rerank candidates, and results from related snapshots can be collapsed by code lineage.
5. The API returns ranked snippets, metadata, score breakdowns, and timing information.

Search results and embeddings can be cached in Redis. If Redis is unavailable, CodeLens uses an in-memory LRU cache. Index snapshots are also kept in a bounded in-process LRU to reduce repeated disk loads.

## Project layout

```text
backend/
  app/                 FastAPI app, configuration, cache, and API routes
  pipeline/            Query cleanup, chunking, BM25, embeddings, fusion, and lineage
  tests/               Backend unit tests
frontend/
  src/App.tsx           Search workspace and application state
  src/api.ts            Frontend client for the CodeLens API
  src/components/       Search, repository, indexing, history, and README UI
demo_repos/             Small repositories for trying the app
indexes/                Generated versioned index snapshots (not source files)
results/                Evaluation and benchmark output
benchmarks/             Search and indexing benchmark scripts
```

## Run locally

Use Python 3.11 or later, Node.js compatible with the Vite version in `frontend/package.json`, and the Git command-line client available on `PATH`. Remote repository indexing needs network access to GitHub; the first index may also download the configured embedding model from Hugging Face.

### 1. Start the backend

From the `backend` directory, create and activate a virtual environment, install the dependencies, and start FastAPI:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs); health status is at [http://localhost:8000/api/health](http://localhost:8000/api/health).

### 2. Start the frontend

In a second terminal, from the `frontend` directory:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite forwards `/api` requests to the backend at `http://localhost:8000` by default (see `frontend/vite.config.ts`).

### 3. Index a repository

In the interface, choose **Rebuild Index**, enter a local repository folder path or GitHub repository reference, and start indexing. The job runs in the background; the frontend shows progress and refreshes repository and snapshot data when it completes. You can also start a job with the API:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/index `
  -ContentType 'application/json' `
  -Body '{"repo_path":"../demo_repos/ecommerce-platform"}'
```

The response includes a `job_id`. Poll `GET /api/index/status?job_id=<job_id>` until its status is `done` or `error`, then search the indexed repository.

> The first indexing or search operation may take longer while the configured embedding model is loaded or downloaded. Runtime speed depends on the repository size, model, and hardware; CodeLens does not guarantee a fixed search latency.

## API overview

| Endpoint | Purpose |
| --- | --- |
| `POST /api/search` | Search with a JSON query, repository/version scope, result limit, and retrieval options. |
| `GET /api/search?q=...` | Search using query-string parameters. |
| `POST /api/index` | Start a background indexing job for a local path or GitHub repository. |
| `GET /api/index/status?job_id=...` | Read indexing job progress, status, and errors. |
| `GET /api/repos` | List repositories with completed indexes and searchable code chunks. |
| `GET /api/versions` | List indexed commit snapshots and their metadata. |
| `GET /api/versions/history/{file_path}` | Read available historical snippets for a file path. |
| `GET /api/lineage/{lineage_id}` | Read lineage history and diffs for a chunk lineage ID. |
| `GET /api/snippet/{chunk_id}` | Retrieve a specific indexed chunk. |
| `GET /api/readme/analyze?repo_path=...` | Analyze a repository README and return summary, features, modules, and suggested questions. |
| `POST /api/readme/analyze` | Analyze a README using a JSON `repo_path`. |
| `GET /api/readme/content?repo_path=...` | Return the README text for a repository. |
| `GET /api/health` | Report API, index, and cache health information. |
| `GET /api/eval` | Return evaluation and rebuild-time results when output files are available. |

## Configuration

Backend settings are defined in `backend/app/config.py` and can be overridden with environment variables or a `.env` file in the backend working directory. Common settings include:

- `EMBED_MODEL` and `EMBED_MODEL_FALLBACK`: dense embedding model identifiers.
- `RERANKER_MODEL`: cross-encoder model used for reranking.
- `USE_BM25`, `USE_HYBRID`, `USE_RERANK`, `USE_QUERY_CLEAN`: retrieval pipeline switches.
- `INDEXES_DIR` and `RESULTS_DIR`: locations for generated index snapshots and evaluation outputs.
- `REDIS_URL`, `CACHE_TTL_SECONDS`, and `QUERY_CACHE_MAX_SIZE`: cache connection and limits.

See `backend/app/config.py` for the complete list and default values. Redis is optional; the cache falls back to memory when Redis cannot be reached.

## Benchmarks and tests

Benchmark and evaluation scripts are in `benchmarks/`. Backend tests are in `backend/tests/` and can be run from the `backend` directory with:

```powershell
python -m pytest
```

