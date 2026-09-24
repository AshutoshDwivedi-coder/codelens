"""
bm25.py – BM25 sparse retrieval index for CodeLens.

Uses the `bm25s` library (faster than rank_bm25, supports batch scoring).
Falls back to a pure-Python BM25Okapi from rank_bm25 if bm25s is absent.

The index is built over tokenised chunk text (symbol_name + docstring + code).
"""
from __future__ import annotations

import json
import logging
import math
import pickle
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("codelens.bm25")

# ──────────────────────────── Library selection ────────────────────────────

try:
    import bm25s as _bm25s_lib
    _BM25S_AVAILABLE = True
    logger.info("Using bm25s for BM25 index")
except ImportError:
    _BM25S_AVAILABLE = False
    logger.warning("bm25s not installed. Trying rank_bm25 fallback.")

if not _BM25S_AVAILABLE:
    try:
        from rank_bm25 import BM25Okapi as _BM25Okapi
        _RANK_BM25_AVAILABLE = True
        logger.info("Using rank_bm25 (BM25Okapi) for BM25 index")
    except ImportError:
        _RANK_BM25_AVAILABLE = False
        logger.warning(
            "Neither bm25s nor rank_bm25 installed.\n"
            "Install with: pip install bm25s  OR  pip install rank-bm25\n"
            "BM25 search will be unavailable."
        )


# ──────────────────────────── Tokeniser ────────────────────────────────────

_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*|\d+")


def tokenise(text: str) -> list[str]:
    """
    Code-aware tokenizer: extracts alphanumeric tokens, lowercases them, and
    splits camelCase and snake_case identifiers into constituent subwords for BM25 recall.
    """
    if not text:
        return []
    # Split camelCase (e.g., parseJSON -> parse JSON)
    text_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    # Split snake_case and non-alphanumeric separators
    text_clean = re.sub(r"[_\.\-\/\:\\]", " ", text_split)
    
    tokens = re.findall(r"[a-zA-Z0-9]+", text_clean.lower())
    # Keep tokens between length 2 and 60
    return [t for t in tokens if 2 <= len(t) <= 60]


# ──────────────────────────── BM25Index class ──────────────────────────────


class BM25Index:
    """
    BM25 retrieval index over a list of code chunks.

    Parameters
    ----------
    chunks:  list of chunk dicts (or CodeChunk objects) with a 'text' field
    """

    def __init__(self) -> None:
        self._chunks: list[dict] = []
        self._bm25 = None  # underlying index object
        self._corpus_tokens: list[list[str]] = []

    def build(self, chunks: list, text_fn=None) -> None:
        """
        Build the BM25 index from *chunks*.

        Parameters
        ----------
        chunks:   list of chunk dicts or CodeChunk objects
        text_fn:  callable(chunk) → str; defaults to concatenating
                  symbol_name + docstring + code
        """
        if text_fn is None:
            def text_fn(c):
                parts = []
                for attr in ("symbol_name", "docstring", "code"):
                    val = c.get(attr, "") if isinstance(c, dict) else getattr(c, attr, "")
                    if val:
                        parts.append(val)
                return "\n".join(parts)

        self._chunks = []
        corpus_tokens: list[list[str]] = []

        for chunk in chunks:
            text = text_fn(chunk)
            toks = tokenise(text)
            corpus_tokens.append(toks)
            meta = chunk if isinstance(chunk, dict) else {
                "chunk_id": getattr(chunk, "chunk_id", ""),
                "content_hash": getattr(chunk, "content_hash", ""),
                "lineage_id": getattr(chunk, "lineage_id", ""),
                "file_path": getattr(chunk, "file_path", ""),
                "symbol_name": getattr(chunk, "symbol_name", ""),
                "signature": getattr(chunk, "signature", ""),
                "docstring": getattr(chunk, "docstring", ""),
                "language": getattr(chunk, "language", ""),
                "chunk_type": getattr(chunk, "chunk_type", "block"),
                "start_line": getattr(chunk, "start_line", 1),
                "end_line": getattr(chunk, "end_line", 1),
                "code": getattr(chunk, "code", ""),
                "tags": getattr(chunk, "tags", {}),
            }
            self._chunks.append(meta)

        self._corpus_tokens = corpus_tokens
        self._build_index(corpus_tokens)
        logger.info("BM25 index built: %d documents", len(self._chunks))

    def _build_index(self, corpus_tokens: list[list[str]]) -> None:
        if not corpus_tokens:
            return

        if _BM25S_AVAILABLE:
            self._bm25 = _bm25s_lib.BM25()
            self._bm25.index(corpus_tokens)
        elif _RANK_BM25_AVAILABLE:
            self._bm25 = _BM25Okapi(corpus_tokens)
        else:
            # Pure-python BM25 fallback (very slow for large corpora)
            self._bm25 = _PurePythonBM25(corpus_tokens)

    def search(self, query: str, top_k: int = 100) -> list[tuple[float, dict]]:
        """
        Return (score, chunk_dict) pairs, sorted by descending BM25 score.
        """
        if self._bm25 is None or not self._chunks:
            return []

        query_tokens = tokenise(query)
        if not query_tokens:
            return []

        if _BM25S_AVAILABLE:
            query_str = " ".join(query_tokens)
            tokenized_query = _bm25s_lib.tokenize([query_str])
            results, scores = self._bm25.retrieve(
                tokenized_query,
                corpus=self._chunks,
                k=min(top_k, len(self._chunks)),
            )
            # bm25s returns arrays; flatten to list
            return [
                (float(s), r)
                for s, r in zip(scores[0], results[0])
                if float(s) > 0
            ]
        else:
            # rank_bm25 or pure-python
            scores = self._bm25.get_scores(query_tokens)
            top_ids = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
            return [
                (float(scores[i]), self._chunks[i])
                for i in top_ids
                if scores[i] > 0
            ]

    # ──────────────────────────── Persistence ─────────────────────

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "bm25_chunks.json", "w", encoding="utf-8") as fh:
            json.dump(self._chunks, fh)
        with open(path / "bm25_index.pkl", "wb") as fh:
            pickle.dump({
                "bm25": self._bm25,
                "corpus_tokens": self._corpus_tokens,
            }, fh)
        logger.info("BM25 index saved to %s", path)

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        inst = cls()
        with open(path / "bm25_chunks.json") as fh:
            inst._chunks = json.load(fh)
        with open(path / "bm25_index.pkl", "rb") as fh:
            data = pickle.load(fh)
        inst._bm25 = data["bm25"]
        inst._corpus_tokens = data.get("corpus_tokens", [])
        logger.info("BM25 index loaded from %s (%d docs)", path, len(inst._chunks))
        return inst

    def __len__(self) -> int:
        return len(self._chunks)


# ──────────────────────────── Pure-python BM25 fallback ───────────────────


class _PurePythonBM25:
    """
    Minimal BM25Okapi implementation as last resort.
    """

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.n = len(corpus)
        self.avgdl = sum(len(d) for d in corpus) / max(self.n, 1)
        self._build()

    def _build(self) -> None:
        from collections import Counter, defaultdict
        self.df: dict[str, int] = {}
        self.tf: list[dict[str, float]] = []
        for doc in self.corpus:
            c = Counter(doc)
            self.tf.append({t: f / len(doc) for t, f in c.items()})
            for t in c:
                self.df[t] = self.df.get(t, 0) + 1
        self.idf: dict[str, float] = {
            t: math.log((self.n - df + 0.5) / (df + 0.5) + 1)
            for t, df in self.df.items()
        }

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        scores = [0.0] * self.n
        for i, (doc, tf_doc) in enumerate(zip(self.corpus, self.tf)):
            dl = len(doc)
            for t in query_tokens:
                if t not in self.idf:
                    continue
                tf = tf_doc.get(t, 0.0) * len(doc)
                num = self.idf[t] * tf * (self.k1 + 1)
                den = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[i] += num / max(den, 1e-9)
        return scores
