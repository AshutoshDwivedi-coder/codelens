# CodeLens Backend Service

FastAPI backend server for CodeLens code retrieval.

## Architecture & Endpoints

- `POST /api/search`: Core search endpoint performing BM25 + Dense vector retrieval.
- `POST /api/index`: Triggers asynchronous code repository indexing.
- `GET /api/versions`: Lists indexed git commit versions.
- `GET /api/versions/history/{file_path}`: Returns evolutionary snippet history.
- `GET /api/health`: Health status and cache statistics.

## Key Modules

- `app/services.py`: Retrieval pipeline orchestrator.
- `pipeline/chunking.py`: Tree-sitter AST parser.
- `pipeline/embed.py`: CPU Sentence-Transformer vectorizer.
- `pipeline/bm25.py`: Lexical indexer.
- `pipeline/fusion.py`: Reciprocal Rank Fusion (RRF).
