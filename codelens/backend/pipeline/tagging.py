"""
tagging.py – Tag enrichment for code chunks.

Tags each chunk with:
  - language (from file extension)
  - chunk_type (function / class / block / test / config)
  - is_test (bool)
  - is_config (bool)

Tags are stored in chunk.tags and indexed in BM25 for filter support.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_TEST_FILE_RE = re.compile(r"(test_|_test\.|\.test\.|spec\.)", re.I)
_CONFIG_FILE_RE = re.compile(r"(config|settings|setup|\.env|\.toml|\.yaml|\.yml|\.ini|Dockerfile)", re.I)
_GENERATED_RE = re.compile(r"(generated|auto.?gen|\.pb\.go|\.pb\.py)", re.I)

_TEST_FUNC_RE = re.compile(r"^(test_|Test[A-Z])", re.M)


def tag_chunk(chunk: Any, file_path: str = "") -> dict:
    """
    Return a tags dict for the given chunk object/dict.

    Mutates chunk.tags if chunk has that attribute.
    """
    tags: dict = {}

    # Existing tags from chunker
    existing = getattr(chunk, "tags", {}) if not isinstance(chunk, dict) else chunk.get("tags", {})
    tags.update(existing)

    # File-path based
    fp = file_path or (
        chunk.get("file_path", "") if isinstance(chunk, dict)
        else getattr(chunk, "file_path", "")
    )
    tags["is_test"] = bool(_TEST_FILE_RE.search(fp))
    tags["is_config"] = bool(_CONFIG_FILE_RE.search(fp))
    tags["is_generated"] = bool(_GENERATED_RE.search(fp))

    # Symbol-name based
    sym = (
        chunk.get("symbol_name", "") if isinstance(chunk, dict)
        else getattr(chunk, "symbol_name", "")
    )
    if sym and _TEST_FUNC_RE.match(sym):
        tags["is_test"] = True

    # Code-based (check for common test framework patterns)
    code = (
        chunk.get("code", "") if isinstance(chunk, dict)
        else getattr(chunk, "code", "")
    )
    if any(marker in code for marker in ["@pytest.mark", "unittest.TestCase", "describe(", "it(", "expect("]):
        tags["is_test"] = True

    # Chunk type
    chunk_type = (
        chunk.get("chunk_type", "block") if isinstance(chunk, dict)
        else getattr(chunk, "chunk_type", "block")
    )
    tags["chunk_type"] = chunk_type

    return tags
