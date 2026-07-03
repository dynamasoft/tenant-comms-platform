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
"""Unit tests for schema assembly / markdown rendering (the seven output sections)."""

from __future__ import annotations

from app.config import DISCLAIMER
from app.schemas import AnalysisResult, RetrievalHit


def _sample_result() -> AnalysisResult:
    return AnalysisResult(
        question="The tenant did not pay rent.",
        tone="professional",
        lease_findings="Lease excerpt #2: rent is due on the first.",
        lease_citations=[RetrievalHit(citation="Lease excerpt #2", text="rent due", score=1.0)],
        law_considerations="Fla. Stat. § 83.56(3) requires a 3-day notice.",
        risk_analysis="Serving a defective notice risks dismissal.",
        recommended_next_steps=["Serve a proper 3-day notice."],
        timeline="Deadline 2026-07-08.",
        draft_message_subject="Notice of past-due rent",
        draft_message_body="Dear Tenant, our records show rent is past due.",
        disclaimer=DISCLAIMER,
    )


def test_to_markdown_has_all_seven_sections():
    md = _sample_result().to_markdown()
    for heading in (
        "## 1. Lease Findings",
        "## 2. Florida Law Considerations",
        "## 3. Risk Analysis",
        "## 4. Timeline / Deadlines",
        "## 5. Recommended Next Steps",
        "## 6. Draft Tenant Message",
        "## 7. Disclaimer",
    ):
        assert heading in md


def test_markdown_contains_disclaimer_text():
    md = _sample_result().to_markdown()
    assert DISCLAIMER in md


def test_empty_message_and_steps_render_gracefully():
    result = _sample_result()
    result.recommended_next_steps = []
    result.draft_message_subject = ""
    result.draft_message_body = ""
    md = result.to_markdown()
    assert "_None provided._" in md
    assert "_No message drafted._" in md
