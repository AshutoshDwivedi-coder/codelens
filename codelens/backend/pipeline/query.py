"""
query.py – Query analysis and cleaning for the CodeLens retrieval pipeline.

Responsibilities
----------------
1. Categorise the query into one of four types (rule-based, cheap):
   - how_it_works  : "how does X work", "explain Y"
   - where_is      : "where is X", "find function Y"
   - bug_fix       : "fix", "error", "exception", "traceback"
   - problem_stmt  : long natural-language problem statement (APPS-style)

2. Clean / rewrite the query:
   - Strip APPS boilerplate (input/output format sections, sample test cases)
   - Expand contractions
   - Remove special characters except operators useful for code search
   - For very long queries, extract the core task sentence

3. Keyword expansion (second-pass, optional):
   - Add synonyms for common programming terms
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class QueryType(str, Enum):
    HOW_IT_WORKS = "how_it_works"
    WHERE_IS = "where_is"
    BUG_FIX = "bug_fix"
    PROBLEM_STMT = "problem_stmt"
    GENERAL = "general"


# ──────────────────────────── Type detection ───────────────────────────────

_HOW_PATTERNS = [
    re.compile(r"\bhow\s+(does|do|is|to|can|should)\b", re.I),
    re.compile(r"\bexplain\b", re.I),
    re.compile(r"\bwhat\s+is\b", re.I),
    re.compile(r"\bunderstand\b", re.I),
]
_WHERE_PATTERNS = [
    re.compile(r"\bwhere\s+is\b", re.I),
    re.compile(r"\bfind\s+(function|class|method|file)\b", re.I),
    re.compile(r"\blocate\b", re.I),
    re.compile(r"\bshow\s+me\b", re.I),
]
_BUG_PATTERNS = [
    re.compile(r"\b(fix|error|exception|traceback|bug|crash|fail)\b", re.I),
    re.compile(r"\bAttributeError\b|\bTypeError\b|\bValueError\b"),
    re.compile(r"\bsegfault\b|\bsegmentation fault\b", re.I),
]
# APPS-style: long (>80 chars) and contains programming contest markers
_APPS_MARKERS = [
    "input format",
    "output format",
    "sample input",
    "sample output",
    "constraints",
    "examples:",
    "example:",
    "note:",
]


def categorize_query(query: str) -> QueryType:
    """Return the QueryType for *query* using cheap rule-based heuristics."""
    q = query.strip()

    # Long problem statements
    if len(q) > 200 and any(m in q.lower() for m in _APPS_MARKERS):
        return QueryType.PROBLEM_STMT

    for pat in _HOW_PATTERNS:
        if pat.search(q):
            return QueryType.HOW_IT_WORKS

    for pat in _WHERE_PATTERNS:
        if pat.search(q):
            return QueryType.WHERE_IS

    for pat in _BUG_PATTERNS:
        if pat.search(q):
            return QueryType.BUG_FIX

    if len(q) > 150:
        return QueryType.PROBLEM_STMT

    return QueryType.GENERAL


# ──────────────────────────── APPS boilerplate stripping ───────────────────

# Sections to cut; everything from this heading to the next empty line (or EOF)
_BOILERPLATE_SECTIONS = [
    re.compile(r"(?mi)^[-—=*]{3,}.*$"),  # horizontal rules
    re.compile(
        r"(?mi)^(input format|output format|sample input|sample output|"
        r"constraints|examples?|note)[:\s]*$.*?(?=\n\s*\n|\Z)",
        re.DOTALL | re.I,
    ),
    # Remove numeric sample cases: lines starting with digits or "Case X:"
    re.compile(r"(?m)^\s*\d[\d\.\)]*\s.*$"),
    # Remove lines that are pure numbers / punctuation (test case values)
    re.compile(r"(?m)^\s*[\d\s,\[\]\(\)\{\}\-\.]+\s*$"),
]


def strip_apps_boilerplate(text: str) -> str:
    """
    Strip common APPS benchmark boilerplate from a problem statement, keeping
    the core task description (first few paragraphs).
    """
    # Split on double newlines; keep paragraphs that don't look like boilerplate
    paragraphs = re.split(r"\n{2,}", text.strip())
    kept: list[str] = []
    boilerplate_seen = 0

    for para in paragraphs:
        para_lower = para.lower().strip()
        is_boilerplate = any(marker in para_lower for marker in _APPS_MARKERS)
        # Also skip very short numeric-only paragraphs
        is_numeric = bool(re.match(r"^[\d\s,\[\]\(\)\{\}\.\-\+\*\/\n]+$", para.strip()))

        if is_boilerplate or (is_numeric and boilerplate_seen > 0):
            boilerplate_seen += 1
            continue

        kept.append(para)
        if boilerplate_seen > 0 and len(kept) >= 2:
            # After boilerplate section, stop collecting
            break

    result = "\n\n".join(kept)
    # Final cleanup: collapse whitespace
    result = re.sub(r" {2,}", " ", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ──────────────────────────── General cleaning ─────────────────────────────

_CONTRACTION_MAP = {
    "won't": "will not",
    "can't": "cannot",
    "don't": "do not",
    "doesn't": "does not",
    "isn't": "is not",
    "wasn't": "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't": "has not",
    "hadn't": "had not",
    "wouldn't": "would not",
    "shouldn't": "should not",
    "couldn't": "could not",
    "mustn't": "must not",
    "i'm": "i am",
    "i've": "i have",
    "i'll": "i will",
    "i'd": "i would",
    "it's": "it is",
    "that's": "that is",
    "there's": "there is",
    "they're": "they are",
    "we're": "we are",
    "we've": "we have",
    "you're": "you are",
    "you've": "you have",
    "let's": "let us",
}

_CONTRACTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _CONTRACTION_MAP) + r")\b",
    re.IGNORECASE,
)


def _expand_contractions(text: str) -> str:
    def _replace(m: re.Match) -> str:
        return _CONTRACTION_MAP[m.group(0).lower()]
    return _CONTRACTION_RE.sub(_replace, text)


# ──────────────────────────── Keyword expansion ────────────────────────────

_SYNONYM_MAP: dict[str, list[str]] = {
    "sort": ["order", "arrange", "rank"],
    "parse": ["tokenize", "lex", "decode", "deserialize"],
    "serialize": ["encode", "marshal", "dump"],
    "http": ["request", "response", "rest", "api"],
    "async": ["asynchronous", "await", "coroutine", "concurrent"],
    "error": ["exception", "failure", "bug", "crash"],
    "config": ["configuration", "settings", "options"],
    "db": ["database", "sql", "query", "store"],
    "auth": ["authentication", "authorization", "login", "token"],
}


def expand_keywords(query: str) -> str:
    """Append synonym expansions to the query for second-pass retrieval."""
    additions: list[str] = []
    query_lower = query.lower()
    for keyword, synonyms in _SYNONYM_MAP.items():
        if keyword in query_lower:
            additions.extend(synonyms)
    if additions:
        return query + " " + " ".join(additions)
    return query


# ──────────────────────────── Main cleaner ─────────────────────────────────


@dataclass
class CleanedQuery:
    original: str
    cleaned: str
    query_type: QueryType
    was_cleaned: bool


# Phrases that pad recommended / natural-language questions without helping retrieval
_NL_FILLER_RE = re.compile(
    r"\b("
    r"where\s+is|where\s+are|how\s+does|how\s+do|how\s+are|how\s+is|"
    r"what\s+is|what\s+are|show\s+me|find|locate|explain|"
    r"implemented\s+in\s+the\s+codebase|in\s+the\s+codebase|"
    r"step[- ]by[- ]step|in\s+this\s+codebase|in\s+this\s+repository|"
    r"the\s+primary\s+role\s+of|defined\s+for|handled\s+in"
    r")\b",
    re.IGNORECASE,
)


def extract_search_terms(query: str) -> str:
    """
    Rewrite a natural-language / recommended question into retrieval-friendly terms.

    Prefer concrete file paths from backticks and drop filler phrasing so BM25
    and dense search can match indexed symbols and paths.
    """
    paths = re.findall(r"`([^`]+)`", query)
    # Keep path basename tokens (e.g. payment.py → payment) for keyword match
    path_tokens: list[str] = []
    for p in paths:
        path_tokens.append(p)
        name = Path(p).stem if "/" in p or "\\" in p or "." in p else p
        if name and name not in path_tokens:
            path_tokens.append(name)

    text = query
    for p in paths:
        text = text.replace(f"`{p}`", " ")
    text = _NL_FILLER_RE.sub(" ", text)
    # Strip question/exclamation marks only — keep dots in file.ext paths
    text = re.sub(r"[?!]+", " ", text)
    text = re.sub(r"[^\w\s./\\_+-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Drop very short stop-ish leftovers
    stop = {
        "the", "a", "an", "of", "and", "or", "to", "for", "with", "this",
        "that", "in", "on", "at", "is", "are", "does", "do", "work", "works",
    }
    tokens = [t for t in text.split() if t.lower() not in stop and len(t) > 1]
    combined = " ".join(tokens + path_tokens)
    return combined.strip() or query.strip()


def clean_query(
    query: str,
    *,
    expand: bool = False,
) -> CleanedQuery:
    """
    Full query cleaning pipeline.

    Parameters
    ----------
    query:   raw user query
    expand:  whether to apply keyword expansion (second pass)

    Returns
    -------
    CleanedQuery with the cleaned text and detected type.
    """
    qtype = categorize_query(query)
    original = query
    cleaned = query.strip()

    # Expand contractions
    cleaned = _expand_contractions(cleaned)

    # For APPS-style problem statements, strip boilerplate
    if qtype == QueryType.PROBLEM_STMT:
        cleaned = strip_apps_boilerplate(cleaned)

    # Rewrite NL / recommended questions into keyword+path search terms
    if qtype in (QueryType.WHERE_IS, QueryType.HOW_IT_WORKS, QueryType.GENERAL):
        if "`" in cleaned or _NL_FILLER_RE.search(cleaned):
            rewritten = extract_search_terms(cleaned)
            if rewritten:
                cleaned = rewritten

    # Remove control characters, keep newlines
    cleaned = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", " ", cleaned)

    # Collapse excess whitespace
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()

    # Optional keyword expansion
    if expand:
        cleaned = expand_keywords(cleaned)

    was_cleaned = cleaned != original.strip()
    return CleanedQuery(
        original=original,
        cleaned=cleaned,
        query_type=qtype,
        was_cleaned=was_cleaned,
    )
