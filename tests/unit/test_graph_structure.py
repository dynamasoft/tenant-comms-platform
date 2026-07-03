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
"""Structural tests for the real workflow graph (no model calls)."""

from __future__ import annotations

from google.adk.workflow import Workflow

from app.agent import app, root_agent
from app.workflow import build_workflow


def test_root_agent_is_a_workflow():
    assert isinstance(root_agent, Workflow)


def test_app_name_matches_directory():
    # App(name=...) must equal the agent directory name ("app") or eval breaks.
    assert app.name == "app"


def test_build_workflow_is_valid_and_named():
    wf = build_workflow()
    assert wf.name == "tenant_comms"


def test_exactly_one_explicit_tool_in_the_graph():
    """Only timeline_calculator is an explicit tool anywhere in the graph.

    (MCP tools are provided via McpToolset, not counted as an explicit project tool.)
    """
    from app import nodes

    timeline_agent = nodes.make_timeline_agent()
    tool_names = {getattr(t, "__name__", getattr(t, "name", "")) for t in timeline_agent.tools}
    assert "timeline_calculator" in tool_names

    # The other pure-reasoning agents carry no explicit function tools.
    assert not nodes.make_risk_agent().tools
    assert not nodes.make_message_agent().tools
