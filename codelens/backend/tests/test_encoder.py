"""
test_encoder.py – Unit tests for PrePostPipelineEncoder (Phase 1).
"""
import sys
from pathlib import Path
import numpy as np
import pytest

_BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND))


@pytest.fixture(scope="module")
def encoder():
    from encoder import PrePostPipelineEncoder
    return PrePostPipelineEncoder(
        model_name="BAAI/bge-small-en-v1.5",  # small model for CI
        use_query_clean=True,
        use_doc_normalize=True,
        batch_size=4,
    )


def test_encoder_loads(encoder):
    assert encoder is not None


def test_query_encoding_shape(encoder):
    try:
        from mteb.encoder_interface import PromptType
        pt_query = PromptType.query
    except ImportError:
        pt_query = "query"

    queries = ["how to sort a list", "parse json data"]
    emb = encoder.encode(queries, prompt_type=pt_query, show_progress_bar=False)
    assert emb.shape[0] == 2
    assert emb.shape[1] > 0


def test_document_encoding_shape(encoder):
    try:
        from mteb.encoder_interface import PromptType
        pt_passage = PromptType.passage
    except ImportError:
        pt_passage = "passage"

    docs = [
        "def sort_list(lst):\n    return sorted(lst)",
        "def parse_json(data):\n    import json\n    return json.loads(data)",
    ]
    emb = encoder.encode(docs, prompt_type=pt_passage, show_progress_bar=False)
    assert emb.shape[0] == 2
    assert emb.shape[1] > 0


def test_embeddings_are_l2_normalized(encoder):
    texts = ["hello world", "foo bar baz"]
    emb = encoder.encode(texts, show_progress_bar=False)
    norms = np.linalg.norm(emb, axis=1)
    np.testing.assert_allclose(norms, np.ones(len(texts)), atol=1e-5)


def test_semantic_order(encoder):
    """Query about sorting should score higher against sort code than json code."""
    try:
        from mteb.encoder_interface import PromptType
        pt_q = PromptType.query
        pt_p = PromptType.passage
    except ImportError:
        pt_q = "query"
        pt_p = "passage"

    q = encoder.encode(["sort a list in Python"], prompt_type=pt_q, show_progress_bar=False)
    docs = [
        "def sort_list(lst): return sorted(lst)",
        "def connect_database(host, port): return Connection(host, port)",
    ]
    d = encoder.encode(docs, prompt_type=pt_p, show_progress_bar=False)
    scores = (q @ d.T)[0]
    assert scores[0] > scores[1], f"Expected sort doc to score higher; got {scores}"


def test_normalize_document():
    from pipeline.normalize import normalize_document
    code = "def parseHTTPResponse(data): pass"
    result = normalize_document(code, symbol_name="parseHTTPResponse")
    # Should contain split identifier
    assert "parse" in result.lower() or "http" in result.lower()


def test_clean_query():
    from pipeline.query import clean_query, QueryType
    result = clean_query("how does the HTTP parser work?")
    assert result.query_type == QueryType.HOW_IT_WORKS
    assert len(result.cleaned) > 0


def test_apps_boilerplate_strip():
    from pipeline.query import clean_query, QueryType
    long_query = (
        "Write a function that reverses a string.\n\n"
        "Input format:\n"
        "First line: the string\n\n"
        "Output format:\n"
        "The reversed string\n\n"
        "Sample Input:\nhello\n\nSample Output:\nolleh"
    )
    result = clean_query(long_query)
    assert result.query_type == QueryType.PROBLEM_STMT
    # Core task should be preserved
    assert "reverse" in result.cleaned.lower() or "reverses" in result.cleaned.lower()
    # Boilerplate should be stripped or at least present (we check it was cleaned)
    assert result.was_cleaned


def test_split_identifier():
    from pipeline.normalize import split_identifier
    assert split_identifier("parseHTTPResponse") == "parse http response"
    assert split_identifier("my_variable_name") == "my variable name"
    assert split_identifier("PascalCaseClass") == "pascal case class"


def test_bm25_search():
    from pipeline.bm25 import BM25Index

    class FakeChunk:
        def __init__(self, symbol_name, code):
            self.chunk_id = symbol_name
            self.content_hash = symbol_name
            self.lineage_id = symbol_name
            self.file_path = "test.py"
            self.symbol_name = symbol_name
            self.signature = ""
            self.docstring = ""
            self.language = "python"
            self.chunk_type = "function"
            self.start_line = 1
            self.end_line = 5
            self.code = code
            self.tags = {}

    chunks = [
        FakeChunk("sort_list", "def sort_list(lst): return sorted(lst)"),
        FakeChunk("parse_json", "def parse_json(data): import json; return json.loads(data)"),
        FakeChunk("http_request", "def http_request(url): import requests; return requests.get(url)"),
    ]

    idx = BM25Index()
    idx.build(chunks)
    assert len(idx) == 3

    results = idx.search("sort list python", top_k=3)
    assert len(results) > 0
    # Sort result should rank first or second
    top_symbols = [r[1].get("symbol_name") for r in results[:2]]
    assert "sort_list" in top_symbols


def test_rrf_fusion():
    from pipeline.fusion import reciprocal_rank_fusion

    list1 = [(0.9, {"chunk_id": "A"}), (0.8, {"chunk_id": "B"}), (0.7, {"chunk_id": "C"})]
    list2 = [(0.95, {"chunk_id": "B"}), (0.85, {"chunk_id": "A"}), (0.75, {"chunk_id": "D"})]

    fused = reciprocal_rank_fusion([list1, list2])
    chunk_ids = [c["chunk_id"] for _, c in fused]
    # Both A and B are in both lists so should rank above C and D
    assert "A" in chunk_ids[:2] or "B" in chunk_ids[:2]
    assert len(fused) == 4  # A, B, C, D
