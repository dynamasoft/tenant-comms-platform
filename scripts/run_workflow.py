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
"""Run the tenant-comms workflow once, from the terminal or the VS Code debugger.

This is the explicit entrypoint for the "Graph Workflow Debug" launch configuration. Set
breakpoints in app/nodes.py (intake, lease_retrieval, final_response) or app/retrieval.py
and step through a single run.

Usage:
    uv run python scripts/run_workflow.py
    uv run python scripts/run_workflow.py --question "The tenant did not pay rent" --tone firm
    uv run python scripts/run_workflow.py --lease path/to/lease.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

# Ensure UTF-8 console output on Windows so statute § symbols render correctly.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

from app import config  # noqa: E402
from app.workflow import run_workflow  # noqa: E402

DEFAULT_QUESTION = "Tenant moved out without notice and still owes utilities. What should I do?"
DEFAULT_LEASE = PROJECT_ROOT / "fixtures" / "sample_lease.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the tenant-comms workflow once.")
    parser.add_argument("--question", default=DEFAULT_QUESTION, help="Tenant-situation question.")
    parser.add_argument(
        "--tone",
        default=config.DEFAULT_TONE,
        choices=config.TONES,
        help="Tone for the drafted tenant message.",
    )
    parser.add_argument(
        "--lease",
        default=str(DEFAULT_LEASE),
        help="Path to a lease .txt file (use '' for no lease).",
    )
    args = parser.parse_args()

    lease_text = ""
    if args.lease:
        lease_path = Path(args.lease)
        if lease_path.exists():
            lease_text = lease_path.read_text(encoding="utf-8")
        else:
            print(f"[warn] lease file not found: {lease_path} (continuing with no lease)")

    print(f"Question: {args.question}")
    print(f"Tone:     {args.tone}")
    print(f"Lease:    {'loaded (' + str(len(lease_text)) + ' chars)' if lease_text else 'none'}")
    print("Running workflow (calls Gemini + the Florida-law MCP server)...\n")

    result = run_workflow(lease_text, args.question, args.tone)
    print(result.to_markdown())


if __name__ == "__main__":
    main()
