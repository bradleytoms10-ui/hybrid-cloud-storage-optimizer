"""Deterministic tests for milestone parsing and timeline alignment.

All tests pin ``today`` so date math is reproducible.
"""

from datetime import date

from hybrid_cloud_storage_optimizer.tools import timeline

TODAY = date(2026, 6, 12)


# --------------------------------------------------------------------------- #
# Milestone parsing
# --------------------------------------------------------------------------- #
def test_parse_quarter_with_year():
    m = timeline.parse_milestone("Discovery — Q3 2026", today=TODAY)
    assert m.phase == "Assess & Design"
    assert m.display == "Q3 2026"
    assert (m.start, m.end) == (1, 3)  # Jul–Sep 2026 relative to Jun 2026
    assert m.deadline is False


def test_parse_quarter_without_year_resolves_forward():
    # Q1 has already passed in 2026 -> resolves to Q1 2027.
    m = timeline.parse_milestone("Pilot — Q1", today=TODAY)
    assert m.display == "Q1 2027"
    assert m.start == 7  # Jan 2027


def test_parse_half_month_iso_and_year():
    half = timeline.parse_milestone("Cutover — H1 2027", today=TODAY)
    month = timeline.parse_milestone("Cutover — March 2027", today=TODAY)
    iso = timeline.parse_milestone("Cutover — 2027-03", today=TODAY)
    assert half.display == "H1 2027"
    assert month.display == "Mar 2027"
    assert iso.display == "Mar 2027"
    m = timeline.parse_milestone("Full migration — 2027", today=TODAY)
    assert (m.start, m.end) == (7, 18)  # Jan–Dec 2027


def test_parse_relative_phrases():
    nxt = timeline.parse_milestone("Full migration — next year", today=TODAY)
    assert nxt.display == "2027" and nxt.deadline is True  # completion-style label
    early = timeline.parse_milestone("Kickoff — early 2027", today=TODAY)
    assert early.display == "early 2027"
    assert (early.start, early.end) == (7, 10)  # Jan–Apr 2027
    eoy = timeline.parse_milestone("Validation — EOY", today=TODAY)
    assert eoy.display == "Q4 2026"


def test_by_prefix_sets_deadline():
    m = timeline.parse_milestone("cutover by March 2027", today=TODAY)
    assert m.phase == "Cutover" and m.deadline is True


def test_unparseable_returns_none():
    assert timeline.parse_milestone("Pilot — when ready", today=TODAY) is None
    assert timeline.parse_milestone("", today=TODAY) is None


# --------------------------------------------------------------------------- #
# Schedule building
# --------------------------------------------------------------------------- #
def test_schedule_aligns_to_customer_milestones():
    schedule = timeline.build_schedule(
        ["Discovery — Q3 2026", "Pilot — Q4 2026", "Full migration — next year"],
        today=TODAY,
    )
    assert schedule["source"] == "customer_milestones"
    phases = {p["phase"]: p for p in schedule["phases"]}
    assert phases["Assess & Design"]["window"] == "Jul–Sep 2026"
    assert phases["Assess & Design"]["anchored_to"] is not None
    assert phases["Provision & Pilot"]["window"] == "Oct–Dec 2026"
    # "Full migration next year" is a completion deadline -> cutover at end of 2027.
    assert phases["Cutover"]["window"] == "Dec 2027"
    # Interpolated phases fill the gap in order, without overlap regressions.
    assert phases["Seed & Replicate"]["start_month"] >= 7
    assert phases["Validate"]["start_month"] >= phases["Seed & Replicate"]["end_month"]
    assert schedule["conflicts"] == []
    assert len(schedule["schedule_lines"]) == len(timeline.PHASES)


def test_schedule_falls_back_to_standard_template():
    schedule = timeline.build_schedule([], today=TODAY)
    assert schedule["source"] == "standard_template"
    assert sum(p["duration_weeks"] for p in schedule["phases"]) == 12
    assert schedule["phases"][0]["window"] == "Weeks 1–2"

    # Unparseable-only input also falls back, but keeps the strings visible.
    schedule = timeline.build_schedule(["go fast"], today=TODAY)
    assert schedule["source"] == "standard_template"
    assert schedule["unparsed_milestones"] == ["go fast"]


def test_schedule_flags_out_of_order_milestones():
    schedule = timeline.build_schedule(
        ["Pilot — Q1 2027", "Cutover — Q4 2026"], today=TODAY
    )
    assert schedule["conflicts"], "expected a sequencing conflict to be flagged"
    assert "confirm sequencing" in schedule["conflicts"][0]


def test_schedule_keeps_unaligned_milestones_visible():
    schedule = timeline.build_schedule(
        ["Pilot — Q4 2026", "Board review — Q1 2027"], today=TODAY
    )
    assert schedule["source"] == "customer_milestones"
    unaligned = schedule["unaligned_milestones"]
    assert {"label": "Board review", "window": "Q1 2027"} in unaligned


def test_single_deadline_milestone_schedules_preceding_phases():
    schedule = timeline.build_schedule(["Cutover — by March 2027"], today=TODAY)
    phases = {p["phase"]: p for p in schedule["phases"]}
    assert phases["Cutover"]["window"] == "Mar 2027"
    # Everything before cutover fits between now and March 2027, in order.
    order = [p["start_month"] for p in schedule["phases"][:-1]]
    assert order == sorted(order)
    assert phases["Assess & Design"]["start_month"] == 0
    # Optimize follows cutover.
    optimize = phases["Optimize & Decommission"]
    assert optimize["start_month"] > phases["Cutover"]["end_month"] - 1


def test_format_window_spans_years():
    assert timeline.format_window(0, 0, TODAY) == "Jun 2026"
    assert timeline.format_window(1, 3, TODAY) == "Jul–Sep 2026"
    assert timeline.format_window(5, 8, TODAY) == "Nov 2026 – Feb 2027"
