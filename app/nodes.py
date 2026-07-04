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
"""The graph nodes for the Tenant Communication Platform workflow.

Node roles (see workflow.py for how they are wired):
  intake            (function)  — normalize input, chunk the lease
  lease_retrieval   (function)  — keyword search over lease chunks (graph reasoning, no tool)
  florida_law       (LlmAgent)  — Florida law via the local MCP server
  risk_analysis     (LlmAgent)  — compare lease vs law; structured output
  timeline          (LlmAgent)  — the ONE explicit tool: timeline_calculator
  message_draft     (LlmAgent)  — draft landlord-to-tenant message; structured output
  final_response    (function)  — assemble the seven sections + append the disclaimer

Function nodes are plain Python (breakpoints work). The two tool/MCP-using LLM nodes use
`output_key` text rather than `output_schema`, because `output_schema` disables tool calling
in ADK; the pure-reasoning nodes use `output_schema` for robust structured output.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

from app import config
from app.documents import chunk_text
from app.retrieval import search_clauses
from app.schemas import AnalysisResult, DraftMessage, RetrievalHit, RiskAssessment
from app.tools import timeline_calculator

# =========================================================================================
# Function nodes
# =========================================================================================


def _text_of(node_input: Any) -> str:
    """Extract plain text from a node input that may be a str or types.Content."""
    if node_input is None:
        return ""
    if isinstance(node_input, str):
        return node_input
    parts = getattr(node_input, "parts", None)
    if parts:
        return " ".join(p.text for p in parts if getattr(p, "text", None)).strip()
    return str(node_input)


def intake(ctx: Context, node_input: Any) -> Event:
    """Normalize the question, tone, and lease, and chunk the lease text once."""
    question = _text_of(node_input).strip() or ctx.state.get("question", "")
    lease_text = ctx.state.get("lease_text", "") or ""
    tone = ctx.state.get("tone", config.DEFAULT_TONE) or config.DEFAULT_TONE
    if tone not in config.TONES:
        tone = config.DEFAULT_TONE
    chunks = chunk_text(lease_text)
    today = ctx.state.get("today") or datetime.date.today().isoformat()
    return Event(
        output=question,
        state={
            "question": question,
            "tone": tone,
            "today": today,
            "chunks": chunks,
        },
    )


def lease_retrieval(ctx: Context, node_input: Any) -> Event:
    """Search the uploaded lease for clauses relevant to the question (graph reasoning)."""
    question = ctx.state.get("question", "") or _text_of(node_input)
    chunks: list[str] = ctx.state.get("chunks", []) or []
    hits = search_clauses(question, chunks, top_k=3)

    if not chunks:
        lease_findings = (
            "No lease document was provided, so lease-specific clauses could not be "
            "retrieved. Findings below rely on Florida law only."
        )
    elif not hits:
        lease_findings = (
            "A lease was provided, but no clause clearly matched this situation. Review the "
            "lease manually for relevant terms."
        )
    else:
        lines = [
            "Relevant lease passages (cited verbatim from the uploaded document):",
            "",
        ]
        for h in hits:
            lines.append(f"- {h['citation']}: \"{h['text']}\"")
        lease_findings = "\n".join(lines)

    return Event(
        output=question,
        state={
            "lease_findings": lease_findings,
            "lease_citations": hits,
        },
    )


def final_response(ctx: Context, node_input: Any) -> Iterator[Event]:
    """Assemble the seven sections and ALWAYS append the disclaimer (in code, not the LLM)."""
    risk = ctx.state.get("risk") or {}
    draft = ctx.state.get("draft") or {}
    citations = [
        RetrievalHit(citation=h["citation"], text=h["text"], score=h.get("score", 0.0))
        for h in (ctx.state.get("lease_citations") or [])
    ]

    result = AnalysisResult(
        question=ctx.state.get("question", ""),
        tone=ctx.state.get("tone", config.DEFAULT_TONE),
        lease_findings=ctx.state.get("lease_findings")
        or "No lease findings were produced.",
        lease_citations=citations,
        law_considerations=ctx.state.get("law_findings")
        or "No Florida law findings were produced.",
        risk_analysis=(risk.get("risk_analysis") if isinstance(risk, dict) else None)
        or "No risk analysis was produced.",
        recommended_next_steps=(
            risk.get("recommended_next_steps") if isinstance(risk, dict) else None
        )
        or [],
        timeline=ctx.state.get("timeline_findings")
        or "No timeline/deadline calculation was applicable to this question.",
        draft_message_subject=(draft.get("subject") if isinstance(draft, dict) else "") or "",
        draft_message_body=(draft.get("body") if isinstance(draft, dict) else "") or "",
        disclaimer=config.DISCLAIMER,
    )

    result_dict = result.model_dump()
    # A user-facing Content event so playground / `agents-cli run` render the full answer.
    yield Event(
        content=types.Content(
            role="model", parts=[types.Part.from_text(text=result.to_markdown())]
        )
    )
    # The machine-readable result for run_workflow / tests / evals.
    yield Event(output=result_dict, state={"analysis_result": result_dict})


# =========================================================================================
# LLM agent node factories (called once when the workflow is built)
# =========================================================================================


def make_florida_law_agent() -> LlmAgent:
    """Florida law node — queries the local MCP server. No output_schema (uses a tool)."""
    command, args = config.mcp_command()
    florida_law_mcp = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(command=command, args=args),
        ),
        tool_filter=["lookup_florida_law"],
    )
    return LlmAgent(
        name="florida_law",
        model=config.make_model(),
        include_contents="none",
        tools=[florida_law_mcp],
        instruction=(
            "You research Florida residential landlord-tenant law. Use the "
            "`lookup_florida_law` tool to find statutes relevant to this situation:\n"
            "'{question}'\n\n"
            "Then summarize ONLY what the tool returned. Rules:\n"
            "- Cite statute numbers (e.g., Fla. Stat. § 83.56) for each point.\n"
            "- Report Florida law ONLY here. Do NOT restate lease-specific terms — those are "
            "handled in a separate section.\n"
            "- If the tool returns no on-point results, say so plainly; do NOT invent law.\n"
            "- State uncertainty where the law is fact-specific.\n"
            "- You are not a lawyer; do not claim to be one, and do not add a disclaimer "
            "(one is added separately)."
        ),
        output_key="law_findings",
    )


def make_risk_agent() -> LlmAgent:
    """Risk analysis node — compares lease vs law. Structured output (no tools)."""
    return LlmAgent(
        name="risk_analysis",
        model=config.make_model(),
        include_contents="none",
        instruction=(
            "You are a cautious landlord-operations analyst (NOT a lawyer). Compare the "
            "landlord's lease findings against the Florida law findings and assess risk for "
            "the landlord's situation: '{question}'.\n\n"
            "LEASE FINDINGS:\n{lease_findings}\n\n"
            "FLORIDA LAW FINDINGS:\n{law_findings}\n\n"
            "In `risk_analysis`: explain where the lease and law agree or conflict, and the "
            "risks of acting (e.g., defective notice, prohibited self-help). Be explicit "
            "about uncertainty and avoid overconfidence. In `recommended_next_steps`: give "
            "concrete, conservative, lawful steps. Never recommend self-help eviction, "
            "lockouts, or utility shutoffs. Do not claim to be a lawyer."
        ),
        output_schema=RiskAssessment,
        output_key="risk",
    )


def make_timeline_agent() -> LlmAgent:
    """Timeline node — the ONLY explicit tool in the project: timeline_calculator."""
    return LlmAgent(
        name="timeline",
        model=config.make_model(),
        include_contents="none",
        instruction=(
            "You determine landlord/tenant deadlines for this situation: '{question}'. "
            "Today is {today}.\n\n"
            "If (and only if) the situation involves a notice or deadline — a 3-day "
            "pay-or-vacate, 7-day cure, 7-day unconditional, 15-day month-to-month "
            "termination, a lock change, or 'when can I file for eviction' — call the "
            "`timeline_calculator` tool. Choose the correct notice_type. If no service date "
            "is stated, use today ({today}) as the service_date and say so.\n"
            "For a 3-day pay-or-vacate notice, pass include_weekends=false and "
            "exclude_legal_holidays=true. For 7-day and 15-day notices, pass "
            "include_weekends=true and exclude_legal_holidays=false.\n\n"
            "Report the tool's calculated_deadline, explanation, assumptions, and "
            "uncertainty_warning. Do NOT compute court/eviction dates yourself. If no "
            "deadline applies, state that no deadline calculation is needed for this "
            "question. Do not claim to be a lawyer."
        ),
        tools=[timeline_calculator],
        output_key="timeline_findings",
    )


def make_message_agent() -> LlmAgent:
    """Message drafting node — landlord-to-tenant message. Structured output (no tools)."""
    return LlmAgent(
        name="message_draft",
        model=config.make_model(),
        include_contents="none",
        instruction=(
            "Draft a landlord-to-tenant message about this situation: '{question}'.\n"
            "Tone: {tone}.\n\n"
            "Context you may reference at a high level (do not paste it verbatim):\n"
            "LEASE FINDINGS:\n{lease_findings}\n\nFLORIDA LAW FINDINGS:\n{law_findings}\n\n"
            "Rules: be factual and respectful; match the requested tone; reference relevant "
            "lease terms or Florida law only generally; never threaten illegal action "
            "(no lockouts, utility shutoffs, or self-help eviction); do not state a specific "
            "legal deadline unless it was provided; do not claim to be a lawyer; do not "
            "include a legal disclaimer (one is added separately). Provide a short subject "
            "and a complete body."
        ),
        output_schema=DraftMessage,
        output_key="draft",
    )
