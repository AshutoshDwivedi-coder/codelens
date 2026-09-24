# CodeLens Frontend Application

Modern React + Vite + TypeScript web interface for CodeLens, providing CPU-fast code intelligence and natural language search.

## Key Features

- **Natural Language Code Search**: Connects plain-English questions directly to code chunks using hybrid BM25 + dense neural retrieval.
- **Repository Scope Picker**: Filter search scope across multiple codebases or custom repository folders.
- **Version Evolution Viewer**: Visualizes AST diffs and code lineage across historical git commits.
- **Plain English Code Insights**: Automatically displays step-by-step explanations of complex code snippets for non-technical users.
- **README Codebase Analysis**: Reads and analyzes repository README files to generate recommended questions to ask the codebase.

## Component Architecture

- `src/App.tsx`: Root dashboard managing search state, telemetry timers, and modal workflows.
- `src/api.ts`: API client interfacing with FastAPI search, indexer, and README analysis endpoints.
- `src/components/SearchBar.tsx`: Query input, keyboard shortcuts (`/`), alpha weight slider, and hybrid toggle.
- `src/components/RepoSelector.tsx`: Dropdown for selecting repositories, multi-selection, and adding custom repos.
- `src/components/CodeCard.tsx`: Search result card with syntax highlighting and score breakdown.
- `src/components/EvolutionModal.tsx`: AST version diff and structural lineage modal.
- `src/components/IndexingModal.tsx`: Modal to trigger asynchronous repository indexing jobs.
- `src/components/HelpModal.tsx`: Plain-English glossary and query tips.

## Common Codebase Questions

- Where is the search query API call handled in the frontend?
- How is the alpha hybrid slider connected to the retrieval request?
- How does the RepoSelector component manage selected repository state?
- Where is the code syntax highlighting and plain-English explanation rendered?
- How does the EvolutionModal display version diffs between git commits?
