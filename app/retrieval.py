# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Lightweight lease-clause retrieval (TF-IDF-style keyword ranking).

Deliberately dependency-free and deterministic: no embeddings, no network, no vector store.
For a demo-scale lease this keyword ranker is enough to surface the relevant clauses, and it
keeps retrieval fast, offline, and easy to unit-test. This is intentionally NOT an explicit
ADK tool — lease retrieval is handled as part of graph reasoning (an ordinary function node
in the workflow).
"""

from __future__ import annotations

import math
import re

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in",
    "is", "it", "its", "of", "on", "or", "shall", "such", "that", "the", "this", "to",
    "was", "which", "with", "any", "all", "may", "will",
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _idf(chunks_tokens: list[list[str]]) -> dict[str, float]:
    """Inverse document frequency across chunks."""
    n = len(chunks_tokens)
    df: dict[str, int] = {}
    for tokens in chunks_tokens:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    return {term: math.log((n + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}


def search_clauses(query: str, chunks: list[str], top_k: int = 3) -> list[dict]:
    """Return the lease chunks most relevant to a query, with citations.

    Args:
        query: The tenant-situation description or question.
        chunks: Lease chunks produced by ``documents.chunk_text``.
        top_k: Maximum number of clauses to return.

    Returns:
        A list of dicts ordered by descending relevance, each with:
          - ``index``: 0-based chunk index,
          - ``citation``: a stable human label ("Lease excerpt #N"),
          - ``text``: the chunk text,
          - ``score``: the numeric relevance score.
        Chunks with a zero score are omitted. Empty list if there is no lease or no match —
        the caller should then state that no lease passage was found rather than invent one.
    """
    if not chunks:
        return []
    query_terms = _tokenize(query)
    if not query_terms:
        return []

    chunks_tokens = [_tokenize(c) for c in chunks]
    idf = _idf(chunks_tokens)
    q = set(query_terms)

    scored: list[tuple[float, int]] = []
    for i, tokens in enumerate(chunks_tokens):
        if not tokens:
            continue
        tf: dict[str, int] = {}
        for term in tokens:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for term in q:
            if term in tf:
                score += (tf[term] / len(tokens)) * idf.get(term, 1.0)
        if score > 0:
            scored.append((score, i))

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    results = []
    for score, i in scored[: max(0, top_k)]:
        results.append(
            {
                "index": i,
                "citation": f"Lease excerpt #{i + 1}",
                "text": chunks[i],
                "score": round(score, 4),
            }
        )
    return results
