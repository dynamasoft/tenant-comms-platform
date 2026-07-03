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
"""Lightweight eval runner for the Tenant Communication Platform.

Runs the REAL workflow (Gemini + the Florida-law MCP server) on the demo scenarios and
scores each result against transparent heuristics. This complements the native
`agents-cli eval` (LLM-as-judge); it is intentionally simple, deterministic in its scoring,
and fast to read.

Usage:
    uv run python evals/run_evals.py
    uv run python evals/run_evals.py --only did_not_pay_rent lock_change_after_notice
    python evals/run_evals.py --threshold 0.85

Requires Google Cloud credentials (ADC) and the project's .env, because it calls the model.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

# Ensure UTF-8 console output on Windows (statute § symbols, box drawing, etc.).
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

from app.config import DISCLAIMER  # noqa: E402
from app.schemas import AnalysisResult  # noqa: E402
from app.workflow import run_workflow  # noqa: E402
from evals.scenarios import SCENARIOS, Scenario  # noqa: E402

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
LAWYER_RED_FLAGS = (
    "i am a lawyer",
    "i'm a lawyer",
    "i am an attorney",
    "as your attorney",
    "as your lawyer",
    "this is legal advice",
)

# The seven scored criteria (matches the capstone eval spec).
CRITERIA = [
    "cites_lease",
    "separates_law_vs_lease",
    "has_disclaimer",
    "not_a_lawyer",
    "has_next_steps",
    "has_tenant_message",
    "has_deadline_when_applicable",
]


def score_result(result: AnalysisResult, scenario: Scenario) -> dict[str, bool]:
    """Score one assembled result against the seven heuristic criteria."""
    law = result.law_considerations.lower()
    # Text the model actually authored (exclude the code-appended disclaimer).
    authored = " ".join(
        [result.risk_analysis, result.draft_message_body, result.law_considerations]
    ).lower()

    return {
        "cites_lease": bool(result.lease_citations)
        or "lease excerpt" in result.lease_findings.lower(),
        "separates_law_vs_lease": bool(result.lease_findings.strip())
        and bool(result.law_considerations.strip())
        and ("83." in law or "§" in law),
        "has_disclaimer": DISCLAIMER in result.to_markdown(),
        "not_a_lawyer": not any(flag in authored for flag in LAWYER_RED_FLAGS),
        "has_next_steps": len(result.recommended_next_steps) > 0,
        "has_tenant_message": bool(result.draft_message_body.strip()),
        "has_deadline_when_applicable": (
            bool(DATE_RE.search(result.timeline)) if scenario.expects_timeline else True
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight tenant-comms evals.")
    parser.add_argument("--only", nargs="*", help="Only run these scenario ids.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Minimum overall pass rate to exit 0 (default 0.85).",
    )
    args = parser.parse_args()

    lease_text = (PROJECT_ROOT / "fixtures" / "sample_lease.txt").read_text(encoding="utf-8")
    scenarios = SCENARIOS
    if args.only:
        scenarios = [s for s in SCENARIOS if s.id in set(args.only)]
        if not scenarios:
            print(f"No scenarios matched {args.only}. Available: {[s.id for s in SCENARIOS]}")
            return 2

    print("=" * 78)
    print("Tenant Communication Platform — lightweight eval")
    print(f"Scenarios: {len(scenarios)}   Model: real (Gemini via Vertex)   Lease: sample")
    print("=" * 78)

    total_checks = 0
    total_passed = 0
    per_scenario: list[tuple[str, int, int]] = []

    for scenario in scenarios:
        print(f"\n> {scenario.id}: {scenario.question}")
        try:
            result = run_workflow(lease_text, scenario.question, scenario.tone)
        except Exception as exc:  # noqa: BLE001
            print(f"   ERROR running workflow: {exc}")
            per_scenario.append((scenario.id, 0, len(CRITERIA)))
            total_checks += len(CRITERIA)
            continue

        scores = score_result(result, scenario)
        passed = sum(1 for v in scores.values() if v)
        total_passed += passed
        total_checks += len(CRITERIA)
        per_scenario.append((scenario.id, passed, len(CRITERIA)))
        for name in CRITERIA:
            print(f"   [{'PASS' if scores[name] else 'FAIL'}] {name}")

    print("\n" + "=" * 78)
    print("Summary")
    print("-" * 78)
    for sid, passed, total in per_scenario:
        print(f"  {sid:<32} {passed}/{total}")
    overall = (total_passed / total_checks) if total_checks else 0.0
    print("-" * 78)
    print(f"  OVERALL PASS RATE: {total_passed}/{total_checks} = {overall:.0%}")
    print("=" * 78)

    ok = overall >= args.threshold
    print(f"{'PASS' if ok else 'FAIL'} (threshold {args.threshold:.0%})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
