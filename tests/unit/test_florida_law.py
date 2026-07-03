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
"""Unit tests for the pure Florida-law lookup used by the MCP server."""

from __future__ import annotations

import json

from mcp_server.florida_law import load_entries, lookup
from mcp_server.server import lookup_florida_law


def test_kb_parses_multiple_entries():
    entries = load_entries()
    assert len(entries) >= 10
    for e in entries:
        assert e.title and e.statute and e.body


def test_nonpayment_returns_three_day_notice():
    results = lookup("tenant did not pay rent", top_k=3)
    assert results
    assert "83.56(3)" in results[0]["statute"]


def test_lockout_question_finds_prohibited_practices():
    results = lookup("can I change the locks after a 3-day notice", top_k=3)
    statutes = " ".join(r["statute"] for r in results)
    titles = " ".join(r["title"] for r in results)
    assert "83.67" in statutes or "Prohibited" in titles


def test_early_termination_finds_remedies():
    results = lookup("tenant wants to break lease early", top_k=2)
    assert results
    assert "83.595" in results[0]["statute"]


def test_results_sorted_by_score():
    results = lookup("unpaid utilities additional rent", top_k=4)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_no_match_returns_empty():
    assert lookup("photosynthesis of ferns", top_k=3) == []


def test_empty_query_returns_empty():
    assert lookup("", top_k=3) == []


def test_mcp_tool_wrapper_returns_json():
    payload = json.loads(lookup_florida_law("tenant did not pay rent", top_k=2))
    assert "results" in payload
    assert payload["results"]
    assert "disclaimer" in payload
