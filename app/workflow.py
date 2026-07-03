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
"""The ADK 2.0 graph workflow and the single shared `run_workflow` entrypoint.

Graph (sequential — easy to debug, explicit order):

    START -> intake -> lease_retrieval -> florida_law -> risk_analysis
          -> timeline -> message_draft -> final_response

`run_workflow` is the one entrypoint used by the Streamlit UI, scripts/run_workflow.py,
the e2e tests, and the eval runner.
"""

from __future__ import annotations

import asyncio
import datetime

from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.adk.workflow import START, Workflow
from google.genai import types

from app import config, nodes
from app.schemas import AnalysisResult

APP_NAME = "app"  # must match the agent directory name (App(name="app"))


def build_workflow() -> Workflow:
    """Construct the graph. LLM-agent nodes are instantiated once here."""
    florida_law = nodes.make_florida_law_agent()
    risk_analysis = nodes.make_risk_agent()
    timeline = nodes.make_timeline_agent()
    message_draft = nodes.make_message_agent()

    return Workflow(
        name="tenant_comms",
        description="Florida landlord assistant: lease + law + risk + timeline + message.",
        edges=[
            (START, nodes.intake),
            (nodes.intake, nodes.lease_retrieval),
            (nodes.lease_retrieval, florida_law),
            (florida_law, risk_analysis),
            (risk_analysis, timeline),
            (timeline, message_draft),
            (message_draft, nodes.final_response),
        ],
    )


# The root agent the ADK runtime serves (playground, agents-cli run, native eval).
root_agent = build_workflow()
app = App(root_agent=root_agent, name=APP_NAME)


async def run_workflow_async(
    lease_text: str,
    question: str,
    tone: str = config.DEFAULT_TONE,
) -> AnalysisResult:
    """Run the full workflow once and return the assembled result.

    Args:
        lease_text: Extracted lease text ("" if no lease was uploaded).
        question: The landlord's tenant-situation question.
        tone: One of config.TONES for the drafted message.

    Returns:
        The assembled AnalysisResult (all seven sections, disclaimer included).
    """
    runner = InMemoryRunner(app=app)
    today = datetime.date.today().isoformat()
    seed_state = {
        "lease_text": lease_text or "",
        "question": question,
        "tone": tone if tone in config.TONES else config.DEFAULT_TONE,
        "today": today,
        # Placeholders so instruction {state} injection never fails even if a node no-ops.
        "lease_findings": "",
        "law_findings": "",
    }
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id="local", state=seed_state
    )
    message = types.Content(role="user", parts=[types.Part.from_text(text=question)])

    result_dict: dict | None = None
    async for event in runner.run_async(
        user_id="local", session_id=session.id, new_message=message
    ):
        output = getattr(event, "output", None)
        if isinstance(output, dict) and "disclaimer" in output:
            result_dict = output

    if result_dict is None:
        # Fallback: read the assembled result from session state.
        session = await runner.session_service.get_session(
            app_name=APP_NAME, user_id="local", session_id=session.id
        )
        if session is not None:
            result_dict = session.state.get("analysis_result")

    if result_dict is None:
        raise RuntimeError(
            "Workflow completed without producing a final result. Check that the "
            "final_response node ran and that the model/MCP server are reachable."
        )
    return AnalysisResult(**result_dict)


def run_workflow(
    lease_text: str,
    question: str,
    tone: str = config.DEFAULT_TONE,
) -> AnalysisResult:
    """Synchronous wrapper around :func:`run_workflow_async` (for Streamlit / scripts)."""
    try:
        return asyncio.run(run_workflow_async(lease_text, question, tone))
    except RuntimeError as exc:
        # If we're already inside a running event loop, reuse it via nest_asyncio.
        if "event loop is running" not in str(exc).lower():
            raise
        import nest_asyncio  # type: ignore

        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(run_workflow_async(lease_text, question, tone))
