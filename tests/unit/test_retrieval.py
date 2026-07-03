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
"""Unit tests for lightweight lease-clause retrieval."""

from __future__ import annotations

from app.documents import chunk_text
from app.retrieval import search_clauses


def test_empty_inputs_return_empty():
    assert search_clauses("rent", []) == []
    assert search_clauses("", ["some clause"]) == []


def test_ranks_relevant_clause_first():
    chunks = [
        "SECTION 6. Occupancy. Only authorized occupants may reside at the premises.",
        "SECTION 5. Utilities. Tenant is responsible for all utilities as additional rent.",
        "SECTION 1. Term. The lease term is twelve months.",
    ]
    hits = search_clauses("does the unpaid utility count as additional rent?", chunks, top_k=2)
    assert hits, "expected at least one hit"
    assert "Utilities" in hits[0]["text"]
    assert hits[0]["citation"] == "Lease excerpt #2"


def test_scores_descending_and_top_k_respected():
    chunks = [
        "rent rent rent payment due",
        "utilities water electricity",
        "access entry repairs notice",
    ]
    hits = search_clauses("rent payment", chunks, top_k=2)
    assert len(hits) <= 2
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_no_match_returns_empty():
    chunks = ["SECTION 1. Term. Twelve months."]
    assert search_clauses("banana spaceship", chunks) == []


def test_works_on_real_sample_lease(sample_lease_text):
    chunks = chunk_text(sample_lease_text)
    hits = search_clauses("tenant refuses maintenance access for repairs", chunks, top_k=3)
    assert hits
    combined = " ".join(h["text"].lower() for h in hits)
    assert "access" in combined or "enter" in combined
