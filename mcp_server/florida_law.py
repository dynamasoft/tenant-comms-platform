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
"""Pure, importable Florida landlord-tenant law lookup.

This module is deliberately dependency-free and side-effect-free so it can be:
  * imported and unit-tested directly (see tests/unit/test_florida_law.py), and
  * debugged with breakpoints in-process (the MCP *subprocess* in server.py cannot
    be stepped into under the app/Streamlit debugger, but this logic can).

The knowledge base lives in ``data/florida_landlord_tenant.md`` (human-editable). This
module parses that file into entries and scores them against a query with a small,
transparent keyword-overlap ranker (no embeddings, no network).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "florida_landlord_tenant.md"

# Common English words that carry no topical signal for legal keyword matching.
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do", "does",
    "for", "from", "has", "have", "how", "i", "if", "in", "is", "it", "my", "no",
    "not", "of", "on", "or", "still", "that", "the", "their", "them", "they", "this",
    "to", "was", "what", "when", "who", "will", "with", "you", "your", "s",
}


@dataclass
class LawEntry:
    """A single curated statute summary."""

    title: str
    statute: str
    keywords: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    body: str = ""


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _parse_kb(markdown: str) -> list[LawEntry]:
    """Parse the curated markdown into LawEntry records.

    Each entry starts at a line beginning with ``## ``. Lines like ``**Statute:** ...``,
    ``**Keywords:** a, b`` and ``**Topics:** x, y`` are pulled out; everything else in the
    block is the body.
    """
    entries: list[LawEntry] = []
    # Split into blocks on level-2 headings, keeping the heading text.
    blocks = re.split(r"^##\s+", markdown, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        title = lines[0].strip()
        # Skip the top-level document title (level-1 "#", never reaches here) and any
        # block that does not carry a Statute marker (e.g., the intro note).
        statute = ""
        keywords: list[str] = []
        topics: list[str] = []
        body_lines: list[str] = []
        for line in lines[1:]:
            m_stat = re.match(r"\*\*Statute:\*\*\s*(.+)", line)
            m_kw = re.match(r"\*\*Keywords:\*\*\s*(.+)", line)
            m_tp = re.match(r"\*\*Topics:\*\*\s*(.+)", line)
            if m_stat:
                statute = m_stat.group(1).strip()
            elif m_kw:
                keywords = [k.strip() for k in m_kw.group(1).split(",") if k.strip()]
            elif m_tp:
                topics = [t.strip() for t in m_tp.group(1).split(",") if t.strip()]
            else:
                body_lines.append(line)
        if not statute:
            continue  # not a statute entry (intro/header block)
        body = " ".join(" ".join(body_lines).split())
        entries.append(
            LawEntry(
                title=title,
                statute=statute,
                keywords=keywords,
                topics=topics,
                body=body,
            )
        )
    return entries


@lru_cache(maxsize=1)
def load_entries() -> tuple[LawEntry, ...]:
    """Load and cache the knowledge base entries."""
    markdown = DATA_FILE.read_text(encoding="utf-8")
    return tuple(_parse_kb(markdown))


def _score(query_tokens: list[str], query_text: str, entry: LawEntry) -> float:
    """Transparent relevance score for one entry.

    Keyword tokens are weighted highest, then title, then body. A phrase bonus is added
    when a full multi-word keyword phrase appears verbatim in the query.
    """
    if not query_tokens:
        return 0.0
    q = set(query_tokens)
    kw_tokens = set(_tokenize(" ".join(entry.keywords)))
    title_tokens = set(_tokenize(entry.title))
    body_tokens = set(_tokenize(entry.body))

    score = 0.0
    score += 3.0 * len(q & kw_tokens)
    score += 2.0 * len(q & title_tokens)
    score += 1.0 * len(q & body_tokens)

    # Phrase bonuses for multi-word keywords, so a specific concept (e.g. "change locks")
    # outranks entries that merely share a common word (e.g. "notice").
    ql = query_text.lower()
    for kw in entry.keywords:
        kw_tokens_list = _tokenize(kw)
        if len(kw_tokens_list) < 2:
            continue
        if kw.lower() in ql:
            score += 4.0  # exact phrase present verbatim
        elif set(kw_tokens_list).issubset(q):
            score += 3.0  # all words of the keyword present (any order)
    return score


def lookup(query: str, top_k: int = 3) -> list[dict]:
    """Return the top_k most relevant Florida law summaries for a query.

    Args:
        query: A tenant-situation description or legal question.
        top_k: Maximum number of statute summaries to return.

    Returns:
        A list of dicts, each with ``title``, ``statute``, ``summary``, ``topics`` and the
        numeric ``score``, ordered by descending relevance. Entries with a zero score are
        omitted. If nothing matches, returns an empty list (the caller should say so rather
        than invent law).
    """
    query_tokens = _tokenize(query)
    entries = load_entries()
    scored = [
        (_score(query_tokens, query, e), e) for e in entries
    ]
    scored = [(s, e) for s, e in scored if s > 0]
    scored.sort(key=lambda pair: (-pair[0], pair[1].title))
    results = []
    for s, e in scored[: max(0, top_k)]:
        results.append(
            {
                "title": e.title,
                "statute": e.statute,
                "summary": e.body,
                "topics": e.topics,
                "score": round(s, 2),
            }
        )
    return results


if __name__ == "__main__":  # Manual smoke test: `python mcp_server/florida_law.py`
    import json
    import sys

    q = " ".join(sys.argv[1:]) or "tenant did not pay rent and owes utilities"
    print(json.dumps(lookup(q), indent=2))
