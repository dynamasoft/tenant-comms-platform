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
"""Debug the Florida-law lookup DIRECTLY (no LLM, no MCP subprocess, no Streamlit).

This calls the exact same code the `florida_law` graph node reaches through the MCP
server -- but in THIS process, so your breakpoints actually stop.

Set a breakpoint on either:
  * mcp_server/server.py:60      (results = lookup(query, top_k=top_k))  -- the tool wrapper
  * mcp_server/florida_law.py:149 (def lookup)                           -- the real search

Then launch "Debug Florida-Law Lookup" from the Run and Debug panel and step through.

Usage:
    uv run python scripts/debug_law_lookup.py
    uv run python scripts/debug_law_lookup.py --query "can I change the locks after a 3-day notice"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 console output on Windows so statute § symbols render correctly.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

# The MCP tool wrapper -- calling this steps through exactly what the agent triggers.
from mcp_server.server import lookup_florida_law  # noqa: E402

DEFAULT_QUERY = "tenant did not pay rent"


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug the Florida-law lookup directly.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Tenant situation / legal question.")
    parser.add_argument("--top-k", type=int, default=3, help="Max statute summaries to return.")
    args = parser.parse_args()

    print(f"Query: {args.query}")
    print(f"top_k: {args.top_k}\n")

    # <-- Put a breakpoint on the next line, or inside lookup_florida_law / lookup, and step in.
    result_json = lookup_florida_law(query=args.query, top_k=args.top_k)

    print("Raw tool output (the JSON string the agent receives back):\n")
    print(result_json)


if __name__ == "__main__":
    main()
