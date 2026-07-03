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
"""Shared pytest fixtures and an OFFLINE stub-graph harness.

The real workflow's four LLM nodes call Gemini (and one calls the MCP server). To keep the
pytest suite fast, deterministic, and offline, ``run_stub_graph`` swaps those four nodes for
plain function stubs that write the same session-state keys. This still runs the REAL ADK
graph engine and the REAL function nodes we own (intake, lease_retrieval, final_response),
so it verifies graph wiring, state flow, retrieval, and final assembly — without a model.

Behavioral quality of the LLM output is validated separately by the eval layer
(evals/run_evals.py and `agents-cli eval`), never by pytest content assertions.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.runners import InMemoryRunner
from google.adk.workflow import START, Workflow
from google.genai import types

from app import config, nodes
from app.schemas import AnalysisResult

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def sample_lease_text() -> str:
    """The sample residential lease text."""
    return (FIXTURES / "sample_lease.txt").read_text(encoding="utf-8")


# --- Default offline stubs for the four LLM nodes ---------------------------------------


def _stub_law(ctx, node_input):
    return Event(
        output="law",
        state={
            "law_findings": (
                "Under Fla. Stat. § 83.56(3), nonpayment requires a 3-day notice. Under "
                "§ 83.67, self-help eviction and utility shutoffs are prohibited."
            )
        },
    )


def _stub_risk(ctx, node_input):
    return Event(
        output="risk",
        state={
            "risk": {
                "risk_analysis": "Acting without a proper notice risks a defective process.",
                "recommended_next_steps": [
                    "Serve the correct statutory notice.",
                    "Consult a Florida attorney before filing.",
                ],
            }
        },
    )


def _stub_timeline(ctx, node_input):
    return Event(
        output="timeline",
        state={"timeline_findings": "Deadline 2026-07-08, assuming service on 2026-07-03."},
    )


def _stub_no_timeline(ctx, node_input):
    return Event(
        output="timeline",
        state={"timeline_findings": "No deadline calculation is needed for this question."},
    )


def _stub_message(ctx, node_input):
    return Event(
        output="message",
        state={
            "draft": {
                "subject": "Regarding your tenancy",
                "body": "Dear Tenant, we are writing regarding your account. Please contact us.",
            }
        },
    )


DEFAULT_STUBS = {
    "law": _stub_law,
    "risk": _stub_risk,
    "timeline": _stub_timeline,
    "message": _stub_message,
}


def build_stub_workflow(stubs: dict | None = None) -> Workflow:
    """Build the real graph shape with the LLM nodes replaced by function stubs."""
    s = {**DEFAULT_STUBS, **(stubs or {})}
    return Workflow(
        name="tenant_comms_stub",
        edges=[
            (START, nodes.intake),
            (nodes.intake, nodes.lease_retrieval),
            (nodes.lease_retrieval, s["law"]),
            (s["law"], s["risk"]),
            (s["risk"], s["timeline"]),
            (s["timeline"], s["message"]),
            (s["message"], nodes.final_response),
        ],
    )


async def _run_async(workflow: Workflow, lease_text: str, question: str, tone: str) -> AnalysisResult:
    app = App(root_agent=workflow, name="app")
    runner = InMemoryRunner(app=app)
    seed = {
        "lease_text": lease_text,
        "question": question,
        "tone": tone,
        "today": "2026-07-03",
        "lease_findings": "",
        "law_findings": "",
    }
    session = await runner.session_service.create_session(
        app_name="app", user_id="test", state=seed
    )
    message = types.Content(role="user", parts=[types.Part.from_text(text=question)])
    result = None
    async for ev in runner.run_async(
        user_id="test", session_id=session.id, new_message=message
    ):
        out = getattr(ev, "output", None)
        if isinstance(out, dict) and "disclaimer" in out:
            result = out
    assert result is not None, "final_response node did not emit a result"
    return AnalysisResult(**result)


@pytest.fixture
def run_stub_graph():
    """Return a callable that runs the offline stub graph and returns an AnalysisResult."""

    def _run(
        lease_text: str = "",
        question: str = "The tenant did not pay rent.",
        tone: str = config.DEFAULT_TONE,
        stubs: dict | None = None,
    ) -> AnalysisResult:
        workflow = build_stub_workflow(stubs)
        return asyncio.run(_run_async(workflow, lease_text, question, tone))

    return _run
