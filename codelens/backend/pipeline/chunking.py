"""
chunking.py – AST-based code chunking with tree-sitter.

Splits source files into semantically meaningful chunks:
  - Functions / methods
  - Classes (with optional sub-chunking)
  - Top-level blocks

Each chunk carries rich metadata:
  file_path, symbol_name, signature, docstring, language,
  start_line, end_line, chunk_type, lineage_id, content_hash

Falls back to line-based chunking when tree-sitter is unavailable
or when the language grammar is not installed.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("codelens.chunking")

# ──────────────────────────── tree-sitter import ───────────────────────────

try:
    from tree_sitter import Language, Parser
    try:
        import tree_sitter_languages  # optional convenience package
        _TSL_AVAILABLE = True
    except ImportError:
        _TSL_AVAILABLE = False
        logger.warning(
            "tree-sitter-languages not installed; trying individual grammars. "
            "Install with: pip install tree-sitter-languages"
        )
    _TS_AVAILABLE = True
except ImportError:
    _TS_AVAILABLE = False
    logger.warning(
        "tree-sitter not installed; falling back to line-based chunking. "
        "Install with: pip install tree-sitter tree-sitter-languages"
    )


# ──────────────────────────── Language map ─────────────────────────────────

EXTENSION_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".rb": "ruby",
    ".php": "php",
    # Notebook support — cells extracted as Python before chunking
    ".ipynb": "python",
    # Markup / prose — line-based chunking
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".rst": "text",
    # Shell / config
    ".sh": "bash",
    ".bash": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    # Query
    ".sql": "sql",
    # Data science
    ".r": "r",
    ".R": "r",
}

# Node types that represent function-level chunks per language
FUNCTION_NODE_TYPES: dict[str, set[str]] = {
    "python": {"function_definition", "async_function_definition"},
    "javascript": {"function_declaration", "function_expression", "arrow_function", "method_definition"},
    "typescript": {"function_declaration", "function_expression", "arrow_function", "method_definition"},
    "go": {"function_declaration", "method_declaration"},
    "java": {"method_declaration", "constructor_declaration"},
    "rust": {"function_item"},
    "c": {"function_definition"},
    "cpp": {"function_definition"},
    "ruby": {"method", "singleton_method"},
    "php": {"function_definition", "method_declaration"},
}

CLASS_NODE_TYPES: dict[str, set[str]] = {
    "python": {"class_definition"},
    "javascript": {"class_declaration", "class_expression"},
    "typescript": {"class_declaration", "class_expression"},
    "java": {"class_declaration", "interface_declaration"},
    "rust": {"impl_item", "struct_item"},
    "ruby": {"class"},
    "php": {"class_declaration"},
}


# ──────────────────────────── Data model ───────────────────────────────────


@dataclass
class CodeChunk:
    """A single extractable unit of source code."""

    chunk_id: str          # sha256 of (file_path + symbol_name + start_line)
    content_hash: str      # sha256 of raw content (for change detection)
    lineage_id: str        # stable across versions: sha256(file_path + symbol_name)
    file_path: str
    symbol_name: str
    signature: str
    docstring: str
    language: str
    chunk_type: str        # "function" | "class" | "block" | "file"
    start_line: int
    end_line: int
    code: str              # raw source of this chunk
    tags: dict = field(default_factory=dict)  # extra metadata (is_test, etc.)

    @property
    def text_for_embedding(self) -> str:
        """Return the text used for embedding (symbol + docstring + code)."""
        parts = []
        if self.symbol_name:
            parts.append(self.symbol_name)
        if self.docstring:
            parts.append(self.docstring)
        parts.append(self.code)
        return "\n".join(parts)


def _make_chunk_id(file_path: str, symbol_name: str, start_line: int) -> str:
    raw = f"{file_path}::{symbol_name}::{start_line}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _make_lineage_id(file_path: str, symbol_name: str) -> str:
    raw = f"{file_path}::{symbol_name}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _make_content_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()[:32]


# ──────────────────────────── Tree-sitter chunker ──────────────────────────


def _get_ts_language(lang: str) -> Optional[object]:
    """Return the tree-sitter Language object for *lang*, or None."""
    if not _TS_AVAILABLE:
        return None
    if _TSL_AVAILABLE:
        try:
            return tree_sitter_languages.get_language(lang)
        except Exception as exc:
            logger.debug("tree-sitter-languages.get_language(%s) failed: %s", lang, exc)
    return None


def _extract_docstring_from_node(node, source_bytes: bytes, lang: str) -> str:
    """Best-effort docstring extraction from a function/class node."""
    # Python: first string in body
    if lang == "python":
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "expression_statement":
                        for sub in stmt.children:
                            if sub.type in ("string", "concatenated_string"):
                                raw = source_bytes[sub.start_byte:sub.end_byte].decode("utf-8", errors="replace")
                                return raw.strip('"""\'').strip()
    # Generic: look for comment right before the node
    return ""


def _extract_signature(node, source_bytes: bytes) -> str:
    """Extract the function/class signature (first line or up to the body)."""
    text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    # Return first non-empty line (the declaration)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return ""


def _chunk_with_treesitter(
    source: str,
    file_path: str,
    language: str,
    max_chunk_tokens: int = 512,
    min_chunk_lines: int = 3,
) -> list[CodeChunk]:
    """Use tree-sitter to chunk source into function/class nodes."""
    ts_lang = _get_ts_language(language)
    if ts_lang is None:
        return []

    try:
        parser = Parser()
        parser.set_language(ts_lang)
    except Exception as exc:
        logger.debug("Parser setup failed for %s: %s", language, exc)
        return []

    source_bytes = source.encode("utf-8")
    try:
        tree = parser.parse(source_bytes)
    except Exception as exc:
        logger.debug("Parsing failed: %s", exc)
        return []

    chunks: list[CodeChunk] = []
    func_types = FUNCTION_NODE_TYPES.get(language, set())
    class_types = CLASS_NODE_TYPES.get(language, set())

    def visit(node) -> None:
        ntype = node.type
        chunk_type: Optional[str] = None
        if ntype in func_types:
            chunk_type = "function"
        elif ntype in class_types:
            chunk_type = "class"

        if chunk_type:
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            n_lines = end_line - start_line + 1

            if n_lines < min_chunk_lines:
                # still recurse into children
                for child in node.children:
                    visit(child)
                return

            code = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            # Truncate very long chunks
            code_lines = code.splitlines()
            if len(code_lines) > max_chunk_tokens * 2:
                code = "\n".join(code_lines[: max_chunk_tokens * 2])

            # Extract symbol name
            symbol_name = ""
            for child in node.children:
                if child.type in ("identifier", "name"):
                    symbol_name = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                    break

            signature = _extract_signature(node, source_bytes)
            docstring = _extract_docstring_from_node(node, source_bytes, language)

            # Tags
            tags: dict = {}
            is_test = (
                symbol_name.startswith("test_") or
                "test" in file_path.lower() or
                symbol_name.startswith("Test")
            )
            tags["is_test"] = is_test
            tags["language"] = language

            chunk = CodeChunk(
                chunk_id=_make_chunk_id(file_path, symbol_name, start_line),
                content_hash=_make_content_hash(code),
                lineage_id=_make_lineage_id(file_path, symbol_name),
                file_path=file_path,
                symbol_name=symbol_name,
                signature=signature,
                docstring=docstring,
                language=language,
                chunk_type=chunk_type,
                start_line=start_line,
                end_line=end_line,
                code=code,
                tags=tags,
            )
            chunks.append(chunk)
            # Recurse into children for nested functions/classes
            for child in node.children:
                visit(child)
        else:
            for child in node.children:
                visit(child)

    visit(tree.root_node)
    return chunks


# ──────────────────────────── Fallback line chunker ────────────────────────


def _chunk_by_lines(
    source: str,
    file_path: str,
    language: str,
    chunk_size: int = 50,
    overlap: int = 5,
) -> list[CodeChunk]:
    """
    Naive fallback: split by fixed-size line windows.
    Used when tree-sitter is unavailable.
    """
    lines = source.splitlines()
    chunks: list[CodeChunk] = []
    step = chunk_size - overlap

    for i in range(0, max(1, len(lines)), step):
        chunk_lines = lines[i: i + chunk_size]
        code = "\n".join(chunk_lines)
        start_line = i + 1
        end_line = i + len(chunk_lines)
        symbol_name = f"block_{start_line}"

        chunk = CodeChunk(
            chunk_id=_make_chunk_id(file_path, symbol_name, start_line),
            content_hash=_make_content_hash(code),
            lineage_id=_make_lineage_id(file_path, symbol_name),
            file_path=file_path,
            symbol_name=symbol_name,
            signature="",
            docstring="",
            language=language,
            chunk_type="block",
            start_line=start_line,
            end_line=end_line,
            code=code,
            tags={"is_test": False, "language": language},
        )
        chunks.append(chunk)
        if i + chunk_size >= len(lines):
            break

    return chunks


# ──────────────────────────── Notebook extractor ───────────────────────────


def _extract_notebook_source(source: str, file_path: str) -> str:
    """
    Extract Python source from a Jupyter notebook (.ipynb) JSON.

    Concatenates code and markdown cells so the result can be chunked like
    a plain .py file. Returns raw source unchanged on parse failure.
    """
    import json as _json
    try:
        nb = _json.loads(source)
        cells = nb.get("cells", [])
        parts: list[str] = []
        for idx, cell in enumerate(cells):
            ctype = cell.get("cell_type", "")
            src = cell.get("source", [])
            if isinstance(src, list):
                src = "".join(src)
            if not src.strip():
                continue
            if ctype == "code":
                parts.append(f"# --- Cell {idx + 1} ---\n" + src)
            elif ctype in ("markdown", "raw"):
                commented = "\n".join("# " + ln for ln in src.splitlines())
                parts.append(f"# --- Markdown Cell {idx + 1} ---\n" + commented)
        return "\n\n".join(parts) if parts else source
    except Exception:
        return source


# ──────────────────────────── Public API ───────────────────────────────────

# Languages with no tree-sitter grammar — always use line-based chunking
_NON_TS_LANGS = frozenset({"markdown", "text", "bash", "yaml", "toml", "sql", "r", "unknown"})


def chunk_file(
    source: str,
    file_path: str,
    language: Optional[str] = None,
    max_chunk_tokens: int = 512,
    min_chunk_lines: int = 3,
) -> list[CodeChunk]:
    """
    Chunk *source* into CodeChunk objects.

    Tries tree-sitter AST chunking first; falls back to line-based chunking.

    Parameters
    ----------
    source:           raw file content
    file_path:        relative file path (used for lineage_id)
    language:         override language detection
    max_chunk_tokens: soft token cap (in lines) for a single chunk
    min_chunk_lines:  skip chunks shorter than this
    """
    if language is None:
        ext = Path(file_path).suffix.lower()
        language = EXTENSION_TO_LANG.get(ext, "unknown")

    # Jupyter notebook: extract Python source from cells first
    if file_path.endswith(".ipynb"):
        source = _extract_notebook_source(source, file_path)
        language = "python"

    # Try AST chunking (skip for prose/config/data-science languages)
    if _TS_AVAILABLE and language not in _NON_TS_LANGS:
        chunks = _chunk_with_treesitter(
            source, file_path, language,
            max_chunk_tokens=max_chunk_tokens,
            min_chunk_lines=min_chunk_lines,
        )
        if chunks:
            return chunks
        logger.debug("Tree-sitter returned 0 chunks for %s; using line fallback", file_path)

    # Fallback: line-based chunking (works for all langs including prose/config)
    return _chunk_by_lines(source, file_path, language)


def detect_language(file_path: str) -> str:
    """Return the language string for *file_path* based on extension."""
    ext = Path(file_path).suffix.lower()
    return EXTENSION_TO_LANG.get(ext, "unknown")
