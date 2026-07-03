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
"""MCP (Model Context Protocol) stdio server exposing Florida landlord-tenant law lookup.

Thin wrapper over the pure ``florida_law.lookup`` function. The ADK ``florida_law`` graph
node connects to this server over stdio via ``McpToolset`` (see app/config.py for how the
absolute launch path is computed).

Run standalone for debugging:  python mcp_server/server.py   (speaks MCP over stdio)
The actual retrieval logic lives in florida_law.py, which is directly importable and
debuggable without going through the MCP transport.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as a bare script (python mcp_server/server.py): ensure the project root is
# importable so `from mcp_server.florida_law import lookup` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from mcp_server.florida_law import lookup  # noqa: E402

mcp = FastMCP("florida-landlord-tenant-law")


@mcp.tool()
def lookup_florida_law(query: str, top_k: int = 3) -> str:
    """Look up relevant Florida residential landlord-tenant law for a situation or question.

    Searches a curated knowledge base of Florida Statutes Chapter 83, Part II (and closely
    related statutes) and returns the most relevant statute summaries. These are simplified
    educational summaries, not the official statutory text and not legal advice.

    Args:
        query: A description of the tenant situation or a legal question
            (e.g. "tenant did not pay rent", "can I change the locks after a 3-day notice").
        top_k: Maximum number of statute summaries to return (default 3).

    Returns:
        A JSON string with a "results" list of matches (title, statute citation, summary,
        topics, score). If nothing relevant is found, "results" is empty — in that case do
        NOT invent law; say the knowledge base has no on-point provision.
    """
    results = lookup(query, top_k=top_k)
    return json.dumps(
        {
            "query": query,
            "results": results,
            "disclaimer": (
                "Educational summaries of Florida Statutes Ch. 83 Part II. Not the official "
                "statutory text and not legal advice. Verify against the current statute."
            ),
        }
    )


if __name__ == "__main__":
    mcp.run()  # stdio transport by default
