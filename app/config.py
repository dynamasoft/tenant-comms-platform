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
"""Central configuration: model, MCP server launch path, tones, and the disclaimer."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from google.adk.models import Gemini
from google.genai import types

# --- Paths -------------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_SERVER_PATH = PROJECT_ROOT / "mcp_server" / "server.py"

# --- Model -------------------------------------------------------------------------------
# Scaffold default; overridable via MODEL env var. Verified working on Vertex AI (global).
MODEL_NAME = os.getenv("MODEL", "gemini-flash-latest")


def make_model() -> Gemini:
    """Build the Gemini model wrapper (with retries), matching the scaffold's pattern."""
    return Gemini(
        model=MODEL_NAME,
        retry_options=types.HttpRetryOptions(attempts=3),
    )


# --- MCP launch --------------------------------------------------------------------------
def mcp_command() -> tuple[str, list[str]]:
    """Return (command, args) to launch the local Florida-law MCP server over stdio.

    Uses the current interpreter (the project venv) so the server has `mcp` and
    `mcp_server` available. The server prepends the project root to sys.path itself, so cwd
    does not matter.
    """
    return sys.executable, [str(MCP_SERVER_PATH)]


# --- Tones ---------------------------------------------------------------------------------
TONES = ["friendly", "professional", "firm", "final warning"]
DEFAULT_TONE = "professional"

# --- Required disclaimer (appended in code, never left to the LLM) -----------------------
DISCLAIMER = (
    "This is not legal advice. Verify with a Florida attorney or local court before taking "
    "legal action."
)
