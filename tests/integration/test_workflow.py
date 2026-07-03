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
"""Offline end-to-end tests of the graph workflow.

These run the REAL ADK graph engine and the REAL function nodes (intake, lease_retrieval,
final_response) with the four LLM nodes replaced by deterministic stubs (see conftest.py).
They assert STRUCTURE (all seven sections present, disclaimer appended, citations when a
lease is provided, timeline populated when applicable) — not LLM prose. Response quality is
validated by the eval layer instead.
"""

from __future__ import annotations

from app.config import DISCLAIMER, TONES
from tests.conftest import _stub_no_timeline


def _assert_seven_sections(result):
    assert result.lease_findings
    assert result.law_considerations
    assert result.risk_analysis
    assert result.timeline
    assert result.recommended_next_steps  # non-empty list
    assert result.draft_message_body
    assert result.disclaimer == DISCLAIMER


# --- The three required end-to-end scenarios ---------------------------------------------


def test_scenario_moved_out_owes_utilities(run_stub_graph, sample_lease_text):
    result = run_stub_graph(
        lease_text=sample_lease_text,
        question="Tenant moved out without notice and still owes utilities. What should I do?",
        tone="professional",
    )
    _assert_seven_sections(result)
    assert result.lease_citations, "expected cited lease passages when a lease is provided"


def test_scenario_break_lease_early(run_stub_graph, sample_lease_text):
    result = run_stub_graph(
        lease_text=sample_lease_text,
        question="My tenant wants to break the lease early. What are my options?",
        tone="firm",
    )
    _assert_seven_sections(result)
    assert result.tone == "firm"


def test_scenario_did_not_pay_rent(run_stub_graph, sample_lease_text):
    result = run_stub_graph(
        lease_text=sample_lease_text,
        question="The tenant did not pay rent this month. What notice do I serve?",
        tone="final warning",
    )
    _assert_seven_sections(result)
    # Default timeline stub provides a deadline for this notice-driven scenario.
    assert "2026-07-08" in result.timeline


# --- Structural behaviors ----------------------------------------------------------------


def test_no_lease_still_produces_all_sections(run_stub_graph):
    result = run_stub_graph(lease_text="", question="The tenant did not pay rent.")
    _assert_seven_sections(result)
    assert not result.lease_citations
    assert "no lease" in result.lease_findings.lower()


def test_disclaimer_always_present(run_stub_graph, sample_lease_text):
    result = run_stub_graph(lease_text=sample_lease_text, question="Any random question")
    assert DISCLAIMER in result.to_markdown()


def test_timeline_absent_when_not_applicable(run_stub_graph, sample_lease_text):
    result = run_stub_graph(
        lease_text=sample_lease_text,
        question="Does an unpaid utility count as additional rent?",
        stubs={"timeline": _stub_no_timeline},
    )
    _assert_seven_sections(result)
    assert "no deadline" in result.timeline.lower()


def test_invalid_tone_falls_back_to_default(run_stub_graph):
    result = run_stub_graph(question="Any question", tone="sarcastic")
    assert result.tone in TONES
