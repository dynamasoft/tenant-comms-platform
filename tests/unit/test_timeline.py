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
"""Unit tests for the deterministic timeline_calculator tool."""

from __future__ import annotations

from app.tools import florida_legal_holidays, timeline_calculator


def test_three_day_excludes_weekend_and_holiday():
    # Served Fri 2026-07-03. 07-04 is Sat + Independence Day, 07-05 Sun -> skipped.
    # Count Mon 07-06, Tue 07-07, Wed 07-08 -> deadline 07-08.
    r = timeline_calculator(
        "3-day notice to pay rent or vacate", "2026-07-03", False, True, "Orange", ""
    )
    assert r["calculated_deadline"] == "2026-07-08"
    assert "83.56(3)" in r["explanation"]


def test_three_day_from_thursday_skips_weekend():
    # Served Thu 2026-07-09. Count Fri 07-10, (skip Sat/Sun), Mon 07-13, Tue 07-14.
    r = timeline_calculator(
        "3-day notice to pay rent or vacate", "2026-07-09", False, True, "", ""
    )
    assert r["calculated_deadline"] == "2026-07-14"


def test_seven_day_cure_calendar_days():
    r = timeline_calculator("7-day notice to cure", "2026-07-03", True, False, "", "")
    assert r["calculated_deadline"] == "2026-07-10"


def test_seven_day_unconditional_recognized():
    r = timeline_calculator("7-day unconditional notice", "2026-07-03", True, False, "", "")
    assert r["calculated_deadline"] == "2026-07-10"


def test_fifteen_day_warns_about_2023_change():
    r = timeline_calculator(
        "15-day month-to-month termination notice", "2026-07-03", True, False, "", ""
    )
    assert r["calculated_deadline"] == "2026-07-18"
    assert "30" in r["uncertainty_warning"]  # flags the 15 -> 30 day change


def test_custom_deadline_parses_days_from_notes():
    r = timeline_calculator("custom deadline", "2026-07-03", True, False, "", "give 10 days")
    assert r["calculated_deadline"] == "2026-07-13"


def test_custom_without_days_returns_no_date():
    r = timeline_calculator("custom deadline", "2026-07-03", True, False, "", "soon please")
    assert r["calculated_deadline"] is None
    assert r["uncertainty_warning"]


def test_unrecognized_notice_type_is_safe():
    r = timeline_calculator("mystery notice", "2026-07-03", True, False, "", "")
    assert r["calculated_deadline"] is None
    assert r["uncertainty_warning"]


def test_invalid_service_date():
    r = timeline_calculator("3-day notice to pay rent or vacate", "not-a-date", False, True, "", "")
    assert r["calculated_deadline"] is None


def test_never_computes_court_dates_warning():
    r = timeline_calculator("7-day notice to cure", "2026-07-03", True, False, "", "")
    assert "court" in r["uncertainty_warning"].lower()


def test_holidays_include_independence_day():
    holidays = florida_legal_holidays(2026)
    import datetime

    assert datetime.date(2026, 7, 4) in holidays
    assert datetime.date(2026, 1, 1) in holidays
