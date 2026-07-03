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
"""The single explicit ADK tool for this project: ``timeline_calculator``.

Deadline calculation is the one capability that genuinely benefits from deterministic
computation (as opposed to LLM generation), so it is the *only* explicit tool. Everything
else — lease retrieval, Florida law lookup, risk analysis, message drafting — is handled by
graph nodes, MCP context, or LLM reasoning.

The Florida timing logic here is intentionally simple and explicit. It does NOT silently
guess complicated court/eviction deadlines; when a calculation is uncertain it says so in
``uncertainty_warning``.
"""

from __future__ import annotations

import datetime
import re

# --- Notice-type timing rules (simplified; see uncertainty_warning for caveats) ----------
# business_only=True means the statutory count excludes weekends AND legal holidays
# (the Florida 3-day notice, Fla. Stat. § 83.56(3)). The 7-day notices are counted as
# calendar days by default. The include_weekends / exclude_legal_holidays arguments let the
# caller override the counting explicitly.
_NOTICE_RULES: dict[str, dict] = {
    "3-day pay or vacate": {"days": 3, "business_only": True, "cite": "Fla. Stat. § 83.56(3)"},
    "7-day cure": {"days": 7, "business_only": False, "cite": "Fla. Stat. § 83.56(2)(b)"},
    "7-day unconditional": {"days": 7, "business_only": False, "cite": "Fla. Stat. § 83.56(2)(a)"},
    "15-day month-to-month": {"days": 15, "business_only": False, "cite": "Fla. Stat. § 83.57"},
}


def _classify_notice(notice_type: str) -> str | None:
    """Map a free-text notice description to a known rule key (or 'custom' / None)."""
    t = notice_type.lower()
    if "custom" in t:
        return "custom"
    if "cure" in t:
        return "7-day cure"
    if "unconditional" in t or ("7" in t and "cure" not in t) or "seven" in t:
        return "7-day unconditional"
    if "3" in t or "three" in t:
        return "3-day pay or vacate"
    if "15" in t or "fifteen" in t or "month" in t or "termination" in t or "terminate" in t:
        return "15-day month-to-month"
    return None


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime.date:
    """Return the date of the nth given weekday (Mon=0) in a month."""
    d = datetime.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + datetime.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> datetime.date:
    """Return the date of the last given weekday (Mon=0) in a month."""
    if month == 12:
        nxt = datetime.date(year + 1, 1, 1)
    else:
        nxt = datetime.date(year, month + 1, 1)
    last = nxt - datetime.timedelta(days=1)
    return last - datetime.timedelta(days=(last.weekday() - weekday) % 7)


def florida_legal_holidays(year: int) -> set[datetime.date]:
    """Approximate set of Florida legal holidays for a year (fixed + computed dates).

    NOTE: This is a simplified list for demo purposes. It does not model every observed
    holiday, weekend-observance shifts, or county-specific holidays.
    """
    d = datetime.date
    return {
        d(year, 1, 1),                      # New Year's Day
        _nth_weekday(year, 1, 0, 3),        # MLK Day (3rd Mon Jan)
        _last_weekday(year, 5, 0),          # Memorial Day (last Mon May)
        d(year, 6, 19),                     # Juneteenth
        d(year, 7, 4),                      # Independence Day
        _nth_weekday(year, 9, 0, 1),        # Labor Day (1st Mon Sep)
        d(year, 11, 11),                    # Veterans Day
        _nth_weekday(year, 11, 3, 4),       # Thanksgiving (4th Thu Nov)
        d(year, 12, 25),                    # Christmas Day
    }


def _add_days(
    start: datetime.date,
    n: int,
    count_weekends: bool,
    exclude_holidays: bool,
) -> tuple[datetime.date, list[str]]:
    """Advance ``n`` countable days after ``start`` (start day itself is not counted).

    Days that are skipped (weekends when not counted, holidays when excluded) do not count
    toward ``n``. Returns the deadline date and a list of human-readable skip notes.
    """
    cursor = start
    counted = 0
    skipped: list[str] = []
    guard = 0
    while counted < n and guard < 400:
        guard += 1
        cursor += datetime.timedelta(days=1)
        is_weekend = cursor.weekday() >= 5
        is_holiday = exclude_holidays and cursor in florida_legal_holidays(cursor.year)
        if is_weekend and not count_weekends:
            skipped.append(f"{cursor.isoformat()} (weekend, skipped)")
            continue
        if is_holiday:
            skipped.append(f"{cursor.isoformat()} (legal holiday, skipped)")
            continue
        counted += 1
    return cursor, skipped


def timeline_calculator(
    notice_type: str,
    service_date: str,
    include_weekends: bool,
    exclude_legal_holidays: bool,
    county: str,
    notes: str,
) -> dict:
    """Calculate a Florida landlord/tenant notice deadline from a service date.

    Use this ONLY when a deterministic date calculation is needed (e.g. "I served a 3-day
    notice today, when does it expire?", "when can I file for eviction?", "can I change the
    locks yet?"). Do not use it for general legal questions.

    Args:
        notice_type: The kind of notice. One of: "3-day notice to pay rent or vacate",
            "7-day notice to cure", "7-day unconditional notice",
            "15-day month-to-month termination notice", or "custom deadline". Free-text
            variants are matched loosely.
        service_date: The date the notice was served / delivered, as ISO "YYYY-MM-DD".
        include_weekends: Whether weekend days count toward the deadline. For a Florida
            3-day pay-or-vacate notice this should be False (weekends are excluded); for
            7-day and 15-day notices this is normally True (calendar days).
        exclude_legal_holidays: Whether Florida legal holidays are skipped when counting.
            True for the 3-day pay-or-vacate notice; typically False for calendar-day
            notices.
        county: Florida county (used only to note that county-specific holidays are not
            modeled). Pass an empty string if unknown.
        notes: Free-text context. For a "custom deadline", include the number of days
            (e.g. "10 days" or "10 business days"); otherwise used only for context.

    Returns:
        A dict with keys: "calculated_deadline" (ISO date or null), "explanation",
        "assumptions" (list of strings), and "uncertainty_warning".
    """
    assumptions: list[str] = []
    warnings: list[str] = []

    # Parse the service date.
    try:
        start = datetime.date.fromisoformat(service_date.strip())
    except (ValueError, AttributeError):
        return {
            "calculated_deadline": None,
            "explanation": (
                f"Could not parse service_date '{service_date}'. Provide it as an ISO date "
                "like 2026-07-03."
            ),
            "assumptions": [],
            "uncertainty_warning": "No calculation performed because the service date was invalid.",
        }

    kind = _classify_notice(notice_type)

    if kind is None:
        return {
            "calculated_deadline": None,
            "explanation": (
                f"Notice type '{notice_type}' was not recognized. Supported types: 3-day "
                "pay-or-vacate, 7-day cure, 7-day unconditional, 15-day month-to-month "
                "termination, or custom deadline."
            ),
            "assumptions": [],
            "uncertainty_warning": (
                "No calculation performed. Do not guess a deadline for an unrecognized "
                "notice type — confirm the correct notice and timing with a Florida attorney."
            ),
        }

    # Determine day count and counting mode.
    if kind == "custom":
        m = re.search(r"(\d+)\s*(business|calendar)?\s*day", notes.lower())
        if not m:
            return {
                "calculated_deadline": None,
                "explanation": (
                    "A custom deadline needs a number of days. Include it in notes, e.g. "
                    "'10 days' or '10 business days'."
                ),
                "assumptions": [],
                "uncertainty_warning": "No calculation performed — custom day count missing.",
            }
        days = int(m.group(1))
        business_only = m.group(2) == "business"
        cite = "custom / lease-defined"
        assumptions.append(f"Custom deadline of {days} days parsed from notes.")
    else:
        rule = _NOTICE_RULES[kind]
        days = rule["days"]
        business_only = rule["business_only"]
        cite = rule["cite"]

    # The caller's explicit flags override the statutory default counting mode.
    count_weekends = include_weekends
    exclude_holidays = exclude_legal_holidays

    # Sanity nudge: the 3-day pay-or-vacate count statutorily excludes weekends + holidays.
    if kind == "3-day pay or vacate" and (count_weekends or not exclude_holidays):
        warnings.append(
            "The Florida 3-day pay-or-vacate count (§ 83.56(3)) excludes Saturdays, "
            "Sundays, and legal holidays. The flags passed here differ from that default — "
            "double-check whether weekends/holidays should be counted."
        )

    deadline, skipped = _add_days(start, days, count_weekends, exclude_holidays)

    assumptions.append(f"Service date ({start.isoformat()}) is day 0 and is not counted.")
    assumptions.append(
        f"Counted {days} day(s); weekends {'counted' if count_weekends else 'skipped'}, "
        f"legal holidays {'excluded' if exclude_holidays else 'counted'}."
    )
    if exclude_holidays:
        assumptions.append(
            "Legal-holiday list is a simplified Florida set (major state holidays) and may "
            "be incomplete; county-specific and weekend-observed holidays are not modeled."
        )
    if skipped:
        assumptions.append("Skipped days while counting: " + "; ".join(skipped) + ".")
    if county:
        assumptions.append(f"County '{county}' noted; county-specific holidays not modeled.")

    explanation = (
        f"For a {kind} notice ({cite}) served on {start.isoformat()}, counting {days} "
        f"applicable day(s), the deadline is {deadline.isoformat()} "
        f"({deadline.strftime('%A')}). The tenant's time to comply runs through that date."
    )

    # Type-specific uncertainty.
    if kind == "15-day month-to-month":
        warnings.append(
            "Florida's 2023 amendment (effective July 1, 2023) increased month-to-month "
            "termination notice from 15 to at least 30 days. This result uses 15 days — "
            "verify the current requirement and tie the deadline to the end of the rental "
            "period, not just service date + N days."
        )
    warnings.append(
        "This tool computes notice-period expiration only. It does NOT calculate court "
        "filing, hearing, or writ-of-possession dates — those depend on the county and case "
        "and must not be assumed."
    )

    return {
        "calculated_deadline": deadline.isoformat(),
        "explanation": explanation,
        "assumptions": assumptions,
        "uncertainty_warning": " ".join(warnings),
    }
