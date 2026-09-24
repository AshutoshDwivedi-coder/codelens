"""
normalize.py – Document normalization for code chunks.

Applies the following transformations (all toggleable):
  1. camelCase / snake_case identifier splitting
  2. Docstring / comment extraction and prepending
  3. Boilerplate stripping (import-only blocks, auto-generated headers)
  4. Lowercasing and whitespace normalisation for text overlay

Used by both the offline indexer (document side) and the MTEB encoder.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional


# ──────────────────────────── Identifier splitting ─────────────────────────


_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_NONWORD_RE = re.compile(r"[^a-zA-Z0-9\s]")


def split_identifier(name: str) -> str:
    """
    Convert camelCase / snake_case / PascalCase identifiers into space-
    separated lowercase tokens.

    Examples
    --------
    >>> split_identifier("parseHTTPResponse")
    'parse http response'
    >>> split_identifier("my_variable_name")
    'my variable name'
    """
    # split camelCase / PascalCase
    spaced = _CAMEL_RE.sub(" ", name)
    # replace underscores and non-alphanumeric with spaces
    spaced = _NONWORD_RE.sub(" ", spaced)
    return re.sub(r"\s+", " ", spaced).strip().lower()


def split_identifiers_in_text(text: str) -> str:
    """
    Walk every word token in *text* and split identifiers.  Non-identifier
    words (short, numeric) are kept as-is.
    """
    tokens = re.split(r"(\s+)", text)
    result = []
    for tok in tokens:
        if re.match(r"\s+", tok):
            result.append(tok)
        elif len(tok) > 3 and re.search(r"[a-z][A-Z]|_[a-z]", tok):
            result.append(split_identifier(tok))
        else:
            result.append(tok)
    return "".join(result)


# ──────────────────────────── Docstring / comment extraction ───────────────


_TRIPLE_DOUBLE = re.compile(r'"""(.*?)"""', re.DOTALL)
_TRIPLE_SINGLE = re.compile(r"'''(.*?)'''", re.DOTALL)
_BLOCK_COMMENT = re.compile(r"/\*(.*?)\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(?m)^\s*(?:#|//)\s*(.*)")


def extract_docstring(code: str) -> str:
    """
    Return the first docstring or block comment found in *code*, stripped of
    delimiters.  Returns empty string if none found.
    """
    for pattern in (_TRIPLE_DOUBLE, _TRIPLE_SINGLE, _BLOCK_COMMENT):
        m = pattern.search(code)
        if m:
            return m.group(1).strip()
    # Fall back to consecutive line comments at the top
    lines = code.splitlines()
    comment_lines: list[str] = []
    for line in lines:
        m = _LINE_COMMENT.match(line)
        if m:
            comment_lines.append(m.group(1).strip())
        elif line.strip() == "":
            continue
        else:
            break
    return " ".join(comment_lines)


# ──────────────────────────── Boilerplate stripping ────────────────────────


_BOILERPLATE_PATTERNS = [
    # Auto-generated file headers
    re.compile(r"(?mi)^.*auto.?generated.*$"),
    re.compile(r"(?mi)^.*DO NOT EDIT.*$"),
    # Licence headers (first 5 lines only)
    re.compile(r"(?mi)^.*copyright.*$"),
    # Shebang
    re.compile(r"(?m)^#!.*$"),
]


def strip_boilerplate(code: str) -> str:
    """Remove common boilerplate lines from *code*."""
    for pat in _BOILERPLATE_PATTERNS:
        code = pat.sub("", code)
    # Collapse multiple blank lines
    code = re.sub(r"\n{3,}", "\n\n", code)
    return code.strip()


# ──────────────────────────── Main normalizer ──────────────────────────────


def normalize_document(
    code: str,
    symbol_name: Optional[str] = None,
    language: Optional[str] = None,
    *,
    split_ids: bool = True,
    extract_docs: bool = True,
    strip_boiler: bool = True,
) -> str:
    """
    Full document normalisation pipeline.

    Parameters
    ----------
    code:          raw source code of the chunk
    symbol_name:   function/class name if known (prepended as context)
    language:      programming language hint (unused now, reserved)
    split_ids:     whether to split camelCase/snake_case identifiers
    extract_docs:  whether to extract and prepend docstrings
    strip_boiler:  whether to strip boilerplate

    Returns
    -------
    A clean text representation suitable for embedding.
    """
    parts: list[str] = []

    # 1. Prepend symbol name (split) for extra signal
    if symbol_name:
        parts.append(split_identifier(symbol_name))

    # 2. Extract docstring as leading prose
    if extract_docs:
        doc = extract_docstring(code)
        if doc:
            parts.append(doc)

    # 3. Clean source
    clean = strip_boilerplate(code) if strip_boiler else code

    # 4. Split identifiers inside the code
    if split_ids:
        clean = split_identifiers_in_text(clean)

    parts.append(clean)

    return "\n".join(parts)


# ──────────────────────────── Unicode safety ───────────────────────────────


def unicode_normalize(text: str) -> str:
    """NFC normalise and remove non-printable characters."""
    text = unicodedata.normalize("NFC", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cc" or ch in "\n\t")
