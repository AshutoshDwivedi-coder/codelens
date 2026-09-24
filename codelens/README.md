# CodeLens: CPU-Fast, Version-Aware Code Intelligence

CodeLens is a high-performance, CPU-friendly code search and retrieval engine that combines exact lexical matching (BM25) with dense semantic vector embeddings (all-MiniLM-L6-v2) and Reciprocal Rank Fusion (RRF).

## Key Features

- **Hybrid Code Search**: Blends BM25 exact keyword matching with neural sentence-transformer vector embeddings using RRF.
- **AST-Based Code Chunking**: Uses Tree-Sitter to parse Python and TypeScript source code into AST functions, classes, and signatures instead of arbitrary line splits.
- **Version-Aware Evolution Lineage**: Tracks structural code evolution across git commit SHAs, preserving function lineage and diffs over time.
- **Sub-10ms Latency**: Designed for zero-GPU, 100% CPU local deployment with in-memory LRU caching.
- **Plain English Code Descriptions**: Translates complex source code snippets into layperson explanations for non-technical stakeholders.

## System Architecture

1. `backend/app/main.py`: FastAPI server setup with GZip middleware, CORS, and response time headers.
2. `backend/app/services.py`: Main retrieval orchestrator combining BM25, Dense Embeddings, and RRF fusion.
3. `backend/pipeline/chunking.py`: AST chunking using tree-sitter for Python and TypeScript.
4. `backend/pipeline/bm25.py`: Lexical sparse index built with `bm25s` or `rank_bm25`.
5. `backend/pipeline/embed.py`: CPU-optimized dense vector embeddings via HuggingFace sentence-transformers.
6. `backend/pipeline/lineage.py`: Structural code similarity and historical commit tracking.

## Common Codebase Questions

- Where is the search retrieval pipeline initialized?
- How does BM25 lexical search score code chunks?
- Where are dense vector embeddings generated on CPU?
- How does Tree-Sitter parse Python and TypeScript AST nodes?
- How does version lineage track function evolution across git commits?
- Where is FastAPI CORS and lifespan caching configured?
