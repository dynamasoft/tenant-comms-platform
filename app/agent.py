# ruff: noqa
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
"""ADK entrypoint for the Tenant Communication Platform.

The root agent is an ADK 2.0 graph `Workflow` (defined in app/workflow.py):

    START -> intake -> lease_retrieval -> florida_law (MCP) -> risk_analysis
          -> timeline (timeline_calculator tool) -> message_draft -> final_response

`root_agent` and `app` are what the ADK runtime, playground, `agents-cli run`, and native
eval load. The Streamlit UI and scripts use `app.workflow.run_workflow` instead.
"""

from app.workflow import app, root_agent

__all__ = ["app", "root_agent"]
