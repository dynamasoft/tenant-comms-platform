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
"""Eval scenarios for the Tenant Communication Platform (the six demo scenarios)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scenario:
    id: str
    question: str
    tone: str
    expects_timeline: bool  # whether a concrete deadline should appear in the timeline section
    use_lease: bool = True


SCENARIOS: list[Scenario] = [
    Scenario(
        id="moved_out_owes_utilities",
        question="Tenant moved out without notice and still owes utilities. What should I do?",
        tone="professional",
        expects_timeline=False,
    ),
    Scenario(
        id="break_lease_early",
        question="My tenant wants to break the lease early. What are my options and what should I tell them?",
        tone="professional",
        expects_timeline=False,
    ),
    Scenario(
        id="did_not_pay_rent",
        question="The tenant did not pay rent this month. What notice do I serve and when does it expire?",
        tone="firm",
        expects_timeline=True,
    ),
    Scenario(
        id="refuses_maintenance_access",
        question="The tenant refuses to let my contractor in for a repair. Can I require access?",
        tone="professional",
        expects_timeline=False,
    ),
    Scenario(
        id="utility_as_additional_rent",
        question="Does the unpaid utility charge count as additional rent for a 3-day notice?",
        tone="professional",
        expects_timeline=False,
    ),
    Scenario(
        id="lock_change_after_notice",
        question="I served a 3-day notice today. Can I change the locks yet? When can I file for eviction?",
        tone="firm",
        expects_timeline=True,
    ),
]
