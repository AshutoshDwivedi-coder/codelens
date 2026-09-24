"""
encoder.py – MTEB-compatible encoder for CodeLens.

Implements ``PrePostPipelineEncoder(AbsEncoder)`` as required by MTEB.
Uses ``prompt_type`` to branch between query and document paths:

  - PromptType.query    → query cleaning → embed
  - PromptType.passage  → doc normalization → embed

The underlying model is configurable; defaults to
``jinaai/jina-embeddings-v2-base-code`` with a fallback to
``BAAI/bge-small-en-v1.5``.

Post-processing: L2-normalizes all embeddings.  Optionally concatenates
weighted embeddings from two models (set ``secondary_model`` in config).

Usage
-----
    python encoder.py                      # quick self-test
    python run_mteb.py                     # full MTEB eval
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

# ──────────────────────────── Logging ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger("codelens.encoder")

# ──────────────────────────── Add parent to path ───────────────────────────
_BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(_BACKEND_DIR))

from pipeline.normalize import normalize_document, unicode_normalize
from pipeline.query import clean_query

# ──────────────────────────── MTEB imports (guarded) ───────────────────────
try:
    from mteb import AbsTaskRetrieval
    from mteb.encoder_interface import PromptType
    _MTEB_AVAILABLE = True
except ImportError:
    _MTEB_AVAILABLE = False
    logger.warning(
        "mteb not installed – encoder will work standalone but not for MTEB eval. "
        "Install with: pip install mteb"
    )
    # Provide stubs so the rest of the file parses cleanly
    class PromptType:  # type: ignore[no-redef]
        query = "query"
        passage = "passage"

# ──────────────────────────── sentence-transformers ────────────────────────
try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False
    logger.error(
        "sentence-transformers not installed. "
        "Install with: pip install sentence-transformers"
    )


# ═══════════════════════════ Helper functions ═══════════════════════════════


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalise rows of *matrix* in place and return it."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # avoid division by zero
    matrix /= norms
    return matrix


def _load_model(model_name: str) -> "SentenceTransformer":
    """Load a SentenceTransformer model with trust_remote_code for Jina."""
    logger.info("Loading model: %s", model_name)
    t0 = time.perf_counter()
    model = SentenceTransformer(
        model_name,
        trust_remote_code=True,  # required for jinaai models
    )
    dt = time.perf_counter() - t0
    logger.info("Model loaded in %.1f s", dt)
    return model


# ═══════════════════════════ PrePostPipelineEncoder ═══════════════════════


class PrePostPipelineEncoder:
    """
    MTEB-compatible encoder that applies pre- and post-processing around
    a base SentenceTransformer model.

    Parameters
    ----------
    model_name:
        HuggingFace model ID for the primary embedding model.
    secondary_model_name:
        Optional second model; its embeddings are concatenated with
        ``secondary_weight`` to the primary embeddings.
    secondary_weight:
        Weight in [0, 1] applied before concatenation (primary gets 1.0).
    use_query_clean:
        Apply query cleaning on the query side.
    use_doc_normalize:
        Apply document normalisation on the document side.
    batch_size:
        Embedding batch size.
    max_length:
        Token length cap for the encoder.
    """

    def __init__(
        self,
        model_name: str = "jinaai/jina-embeddings-v2-base-code",
        secondary_model_name: Optional[str] = None,
        secondary_weight: float = 0.3,
        use_query_clean: bool = True,
        use_doc_normalize: bool = True,
        batch_size: int = 64,
        max_length: int = 8192,
    ) -> None:
        if not _ST_AVAILABLE:
            raise RuntimeError("sentence-transformers is required")

        self.model_name = model_name
        self.secondary_model_name = secondary_model_name
        self.secondary_weight = secondary_weight
        self.use_query_clean = use_query_clean
        self.use_doc_normalize = use_doc_normalize
        self.batch_size = batch_size
        self.max_length = max_length

        # Load primary model
        try:
            self._model = _load_model(model_name)
        except Exception as exc:
            logger.warning("Primary model failed (%s), falling back to bge-small", exc)
            self._model = _load_model("BAAI/bge-small-en-v1.5")
            self.model_name = "BAAI/bge-small-en-v1.5"

        # Optional secondary model
        self._secondary_model: Optional["SentenceTransformer"] = None
        if secondary_model_name:
            try:
                self._secondary_model = _load_model(secondary_model_name)
                logger.info(
                    "Secondary model loaded: %s (weight=%.2f)",
                    secondary_model_name, secondary_weight,
                )
            except Exception as exc:
                logger.warning("Secondary model failed (%s), skipping", exc)

    # ──────────────────────────── Pre-processing ──────────────────────────

    def _preprocess_queries(self, queries: list[str]) -> list[str]:
        """Apply query cleaning to a list of query strings."""
        if not self.use_query_clean:
            return queries
        cleaned = []
        for q in queries:
            result = clean_query(q)
            cleaned.append(result.cleaned)
        return cleaned

    def _preprocess_documents(self, documents: list[str]) -> list[str]:
        """Apply document normalisation to a list of code strings."""
        if not self.use_doc_normalize:
            return documents
        return [normalize_document(doc) for doc in documents]

    # ──────────────────────────── Core encode ─────────────────────────────

    def _encode_texts(
        self,
        texts: list[str],
        batch_size: int,
        show_progress_bar: bool = True,
        **kwargs: Any,
    ) -> np.ndarray:
        """
        Encode *texts* with the primary model and optionally fuse with the
        secondary model's embeddings.
        """
        embeddings: np.ndarray = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=False,  # we do it ourselves
            **kwargs,
        )

        if self._secondary_model is not None:
            sec_emb: np.ndarray = self._secondary_model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress_bar,
                normalize_embeddings=False,
            )
            # Concatenate: [primary | secondary * weight]
            # L2-normalise each part before concat for fair weighting
            primary_normed = _l2_normalize(embeddings.copy())
            secondary_normed = _l2_normalize(sec_emb.copy()) * self.secondary_weight
            embeddings = np.concatenate([primary_normed, secondary_normed], axis=1)
        else:
            embeddings = _l2_normalize(embeddings)

        return embeddings.astype(np.float32)

    # ──────────────────────────── MTEB interface ──────────────────────────

    def encode(
        self,
        sentences: list[str],
        *,
        prompt_type: Optional[Any] = None,
        batch_size: int = 64,
        show_progress_bar: bool = True,
        **kwargs: Any,
    ) -> np.ndarray:
        """
        MTEB-compatible encode method.

        Branches on ``prompt_type``:
          - PromptType.query   → query cleaning path
          - PromptType.passage → document normalisation path
          - None / other       → no pre-processing
        """
        _batch = batch_size or self.batch_size

        is_query = (prompt_type is not None) and (
            str(prompt_type) in (str(PromptType.query), "query", "PromptType.query")
        )
        is_passage = (prompt_type is not None) and (
            str(prompt_type) in (
                str(PromptType.passage), "passage", "PromptType.passage",
                "document", "PromptType.document",
            )
        )

        if is_query:
            sentences = self._preprocess_queries(sentences)
        elif is_passage:
            sentences = self._preprocess_documents(sentences)

        return self._encode_texts(
            sentences,
            batch_size=_batch,
            show_progress_bar=show_progress_bar,
            **kwargs,
        )

    # Alias for corpora encoding (some MTEB versions call this)
    def encode_corpus(
        self,
        corpus: list[dict[str, str]] | list[str],
        batch_size: int = 64,
        show_progress_bar: bool = True,
        **kwargs: Any,
    ) -> np.ndarray:
        """Encode corpus dicts (MTEB format: {'title': ..., 'text': ...})."""
        if corpus and isinstance(corpus[0], dict):
            texts = [
                (doc.get("title", "") + "\n" + doc.get("text", "")).strip()
                for doc in corpus
            ]
        else:
            texts = list(corpus)  # type: ignore[arg-type]

        return self.encode(
            texts,
            prompt_type=PromptType.passage,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            **kwargs,
        )

    # ──────────────────────────── Properties ──────────────────────────────

    @property
    def embedding_dim(self) -> int:
        """Return the output embedding dimension."""
        sample = self._model.encode(["test"], show_progress_bar=False)
        dim = sample.shape[1]
        if self._secondary_model is not None:
            sec_sample = self._secondary_model.encode(["test"], show_progress_bar=False)
            dim += sec_sample.shape[1]
        return dim

    def __repr__(self) -> str:
        return (
            f"PrePostPipelineEncoder(model={self.model_name!r}, "
            f"secondary={self.secondary_model_name!r}, "
            f"query_clean={self.use_query_clean}, "
            f"doc_normalize={self.use_doc_normalize})"
        )


# ═══════════════════════════ Self-test ════════════════════════════════════


def _self_test() -> None:
    """Quick smoke-test that runs without MTEB."""
    logger.info("Running self-test …")

    enc = PrePostPipelineEncoder(
        model_name="BAAI/bge-small-en-v1.5",  # fast for testing
        use_query_clean=True,
        use_doc_normalize=True,
        batch_size=4,
    )

    queries = [
        "how to sort a list in Python",
        "find function that parses JSON",
    ]
    docs = [
        "def sort_list(lst): return sorted(lst)",
        "def parse_json(data): import json; return json.loads(data)",
    ]

    q_emb = enc.encode(queries, prompt_type=PromptType.query, show_progress_bar=False)
    d_emb = enc.encode(docs, prompt_type=PromptType.passage, show_progress_bar=False)

    logger.info("Query embeddings shape: %s", q_emb.shape)
    logger.info("Doc embeddings shape:   %s", d_emb.shape)

    # Cosine similarity (both are L2-normalised, so dot product = cosine)
    scores = q_emb @ d_emb.T
    logger.info("Similarity matrix:\n%s", np.round(scores, 3))

    # Sanity: diagonal should be higher than off-diagonal for correct encoding
    for i in range(len(queries)):
        assert scores[i, i] >= 0.0, f"Unexpected negative similarity at ({i},{i})"

    logger.info("Self-test passed ✓")


if __name__ == "__main__":
    _self_test()
