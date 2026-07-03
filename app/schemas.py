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
"""Pydantic schemas for structured node output and the assembled final result."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskAssessment(BaseModel):
    """Structured output of the risk_analysis node."""

    risk_analysis: str = Field(
        description="Prose comparing the lease terms against Florida law and identifying "
        "risks to the landlord, with explicit uncertainty where it exists."
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        description="Concrete, conservative next steps the landlord could take.",
    )


class DraftMessage(BaseModel):
    """Structured output of the message_draft node."""

    subject: str = Field(description="A short subject line for the landlord-to-tenant message.")
    body: str = Field(description="The full landlord-to-tenant message body in the chosen tone.")


class RetrievalHit(BaseModel):
    """One cited lease clause."""

    citation: str
    text: str
    score: float


class AnalysisResult(BaseModel):
    """The assembled, display-ready result — the seven output sections."""

    question: str
    tone: str
    lease_findings: str
    lease_citations: list[RetrievalHit] = Field(default_factory=list)
    law_considerations: str
    risk_analysis: str
    recommended_next_steps: list[str] = Field(default_factory=list)
    timeline: str
    draft_message_subject: str = ""
    draft_message_body: str = ""
    disclaimer: str = ""

    def to_markdown(self) -> str:
        """Render the seven sections as markdown (used for CLI/playground display)."""
        steps = "\n".join(f"- {s}" for s in self.recommended_next_steps) or "_None provided._"
        msg = ""
        if self.draft_message_subject or self.draft_message_body:
            subj = f"**Subject:** {self.draft_message_subject}\n\n" if self.draft_message_subject else ""
            msg = f"{subj}{self.draft_message_body}"
        else:
            msg = "_No message drafted._"
        return (
            f"## 1. Lease Findings\n{self.lease_findings}\n\n"
            f"## 2. Florida Law Considerations\n{self.law_considerations}\n\n"
            f"## 3. Risk Analysis\n{self.risk_analysis}\n\n"
            f"## 4. Timeline / Deadlines\n{self.timeline}\n\n"
            f"## 5. Recommended Next Steps\n{steps}\n\n"
            f"## 6. Draft Tenant Message\n{msg}\n\n"
            f"## 7. Disclaimer\n{self.disclaimer}\n"
        )
