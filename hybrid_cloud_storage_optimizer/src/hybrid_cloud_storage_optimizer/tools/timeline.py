"""Timeline alignment: schedule migration phases around the customer's milestones.

Instead of emitting a generic 12-week template, the plan consumes the customer's
stated milestones (e.g. "Discovery — Q3 2026", "Pilot — Q4 2026", "Full
migration — next year") and maps the six canonical migration phases onto those
anchors. Phases without an anchor are interpolated between neighboring anchors;
out-of-order anchors are flagged as conflicts rather than silently reordered.

Framework-free and deterministic: parsing and scheduling take an explicit
``today`` so tests are reproducible. Anything unparseable is surfaced in the
output (never silently dropped) so the architect agent can still acknowledge it.

Granularity is months: storage-migration milestones are almost always stated at
month/quarter level, and a month grid keeps interpolation honest. The standard
template (used when no milestones parse) keeps the original week-level detail.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

# Canonical migration phases, in execution order.
PHASES = (
    "Assess & Design",
    "Provision & Pilot",
    "Seed & Replicate",
    "Validate",
    "Cutover",
    "Optimize & Decommission",
)

# Default months per phase, used for phases scheduled after the last anchor.
_DEFAULT_PHASE_MONTHS = (1, 1, 2, 1, 1, 1)

# Standard fallback template (weeks) when no customer milestones are usable.
STANDARD_TEMPLATE_WEEKS = (
    ("Assess & Design", 2),
    ("Provision & Pilot", 2),
    ("Seed & Replicate", 4),
    ("Validate", 2),
    ("Cutover", 1),
    ("Optimize & Decommission", 1),
)

# Milestone-label tokens -> phase, checked in priority order (first match wins).
# Completion-style tokens ("full migration", "complete") are treated as Cutover
# DEADLINES: the milestone's end month becomes the cutover target.
_PHASE_TOKENS: Sequence[Tuple[Tuple[str, ...], str, bool]] = (
    (("cutover", "cut over", "go-live", "go live", "golive"), "Cutover", False),
    (("optimi", "decommission", "retire", "clean"), "Optimize & Decommission", False),
    (
        ("complete", "completion", "full migration", "finish", "done", "wrap"),
        "Cutover",
        True,
    ),
    (("valid", "uat", "test", "verif"), "Validate", False),
    (
        ("seed", "replicat", "sync", "snapmirror", "transfer", "data move", "copy"),
        "Seed & Replicate",
        False,
    ),
    (
        ("pilot", "poc", "proof", "provision", "landing zone"),
        "Provision & Pilot",
        False,
    ),
    (
        ("assess", "discover", "design", "plan", "requirement", "kickoff", "kick-off"),
        "Assess & Design",
        False,
    ),
    (("migrat",), "Seed & Replicate", False),
)

_MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_MONTH_ABBR = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

_QUARTER_RE = re.compile(r"\bq([1-4])\s*(?:of\s*)?(20\d{2})?\b", re.IGNORECASE)
_HALF_RE = re.compile(r"\bh([12])\s*(?:of\s*)?(20\d{2})?\b", re.IGNORECASE)
_ISO_RE = re.compile(r"\b(20\d{2})[-/](\d{1,2})\b")
_MONTH_RE = re.compile(
    r"\b(" + "|".join(n[:3] for n in _MONTH_NAMES) + r")[a-z]*\.?\s*(20\d{2})?\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_RELATIVE_RE = re.compile(
    r"\b(?:(early|mid|late)\s+)?(next year|this year|20\d{2})\b", re.IGNORECASE
)
_EOY_RE = re.compile(r"\b(?:eoy|end of (?:the )?year)\s*(20\d{2})?\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedMilestone:
    """A customer milestone resolved to a month window relative to ``today``."""

    raw: str
    label: str
    phase: Optional[str]  # canonical phase, or None if unclassifiable
    start: int  # months since the reference month (0 = current month)
    end: int  # inclusive
    deadline: bool  # True => end month is a completion target ("by ...")
    display: str  # the period as the customer stated it, e.g. "Q4 2026"


def _month_index(year: int, month: int, today: date) -> int:
    return (year - today.year) * 12 + (month - today.month)


def _format_month(index: int, today: date) -> str:
    year = today.year + (today.month - 1 + index) // 12
    month = (today.month - 1 + index) % 12 + 1
    return f"{_MONTH_ABBR[month - 1]} {year}"


def format_window(start: int, end: int, today: date) -> str:
    """Human display for a month window, e.g. 'Jul–Sep 2026' or 'Mar 2027'."""
    if start == end:
        return _format_month(start, today)
    first, last = _format_month(start, today), _format_month(end, today)
    if first.split()[1] == last.split()[1]:  # same year -> compact form
        return f"{first.split()[0]}–{last.split()[0]} {first.split()[1]}"
    return f"{first} – {last}"


def _resolve_year(year: Optional[str], end_month: int, today: date) -> int:
    """Use the stated year, else the next occurrence whose window hasn't passed."""
    if year:
        return int(year)
    return today.year if end_month >= today.month else today.year + 1


def _parse_period(text: str, today: date) -> Optional[Tuple[int, int, str]]:
    """Find a period token in ``text``; return (start_idx, end_idx, display)."""
    match = _QUARTER_RE.search(text)
    if match:
        quarter = int(match.group(1))
        first, last = 3 * quarter - 2, 3 * quarter
        year = _resolve_year(match.group(2), last, today)
        return (
            _month_index(year, first, today),
            _month_index(year, last, today),
            f"Q{quarter} {year}",
        )
    match = _HALF_RE.search(text)
    if match:
        half = int(match.group(1))
        first, last = (1, 6) if half == 1 else (7, 12)
        year = _resolve_year(match.group(2), last, today)
        return (
            _month_index(year, first, today),
            _month_index(year, last, today),
            f"H{half} {year}",
        )
    match = _ISO_RE.search(text)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            idx = _month_index(year, month, today)
            return idx, idx, f"{_MONTH_ABBR[month - 1]} {year}"
    match = _MONTH_RE.search(text)
    if match:
        month = next(
            i + 1
            for i, name in enumerate(_MONTH_NAMES)
            if name.startswith(match.group(1).lower())
        )
        year = _resolve_year(match.group(2), month, today)
        idx = _month_index(year, month, today)
        return idx, idx, f"{_MONTH_ABBR[month - 1]} {year}"
    match = _EOY_RE.search(text)
    if match:
        year = int(match.group(1)) if match.group(1) else today.year
        return (
            _month_index(year, 10, today),
            _month_index(year, 12, today),
            f"Q4 {year}",
        )
    match = _RELATIVE_RE.search(text)
    if match:
        modifier, ref = (match.group(1) or "").lower(), match.group(2).lower()
        if ref == "next year":
            year = today.year + 1
        elif ref == "this year":
            year = today.year
        else:
            year = int(ref)
        windows = {"early": (1, 4), "mid": (5, 8), "late": (9, 12), "": (1, 12)}
        first, last = windows[modifier]
        display = f"{modifier + ' ' if modifier else ''}{year}"
        if ref == "this year" and not modifier:
            first = max(first, today.month)  # remainder of the current year
        return (
            _month_index(year, first, today),
            _month_index(year, last, today),
            display,
        )
    return None


def _classify(label: str) -> Tuple[Optional[str], bool]:
    """Map a milestone label to (canonical phase, deadline_flag)."""
    text = label.lower()
    for tokens, phase, deadline in _PHASE_TOKENS:
        if any(token in text for token in tokens):
            return phase, deadline
    return None, False


def parse_milestone(
    text: str, today: Optional[date] = None
) -> Optional[ParsedMilestone]:
    """Parse one milestone string, e.g. 'Pilot — Q4 2026' or 'cutover by March 2027'.

    Returns None when no period token can be found (caller keeps the raw string
    in the ``unparsed`` list rather than dropping it).
    """
    today = today or date.today()
    raw = (text or "").strip()
    if not raw:
        return None
    # Split "Label — period"; fall back to scanning the whole string.
    label, period_text = raw, raw
    for separator in ("—", "–", ":", " - "):
        if separator in raw:
            label, period_text = (part.strip() for part in raw.split(separator, 1))
            break
    parsed = _parse_period(period_text, today) or _parse_period(raw, today)
    if parsed is None:
        return None
    start, end, display = parsed
    phase, deadline = _classify(label if label != raw else raw)
    if re.search(r"\bby\b", raw, re.IGNORECASE):
        deadline = True
    return ParsedMilestone(
        raw=raw,
        label=label,
        phase=phase,
        start=start,
        end=end,
        deadline=deadline,
        display=display,
    )


def _merge_anchor(existing: Optional[dict], milestone: ParsedMilestone) -> dict:
    """Combine multiple milestones that map to the same phase."""
    if existing is None:
        return {
            "start": milestone.start,
            "end": milestone.end,
            "deadline": milestone.deadline,
            "labels": [milestone.label],
            "displays": [milestone.display],
        }
    existing["start"] = min(existing["start"], milestone.start)
    existing["end"] = max(existing["end"], milestone.end)
    existing["deadline"] = existing["deadline"] and milestone.deadline
    existing["labels"].append(milestone.label)
    existing["displays"].append(milestone.display)
    return existing


def _standard_template() -> Dict[str, object]:
    week = 1
    phases = []
    for name, duration in STANDARD_TEMPLATE_WEEKS:
        last = week + duration - 1
        window = f"Week {week}" if week == last else f"Weeks {week}–{last}"
        phases.append(
            {
                "phase": name,
                "window": window,
                "duration_weeks": duration,
                "anchored_to": None,
            }
        )
        week = last + 1
    return {
        "source": "standard_template",
        "phases": phases,
        "milestones_used": [],
        "unparsed_milestones": [],
        "unaligned_milestones": [],
        "conflicts": [],
        "summary": (
            "No customer milestones were provided, so a standard 12-week template "
            "is shown. Confirm target dates in discovery and re-run to align the "
            "plan to the customer's calendar."
        ),
        "schedule_lines": [
            f"{p['phase']}: {p['window']}" for p in phases
        ],
    }


def build_schedule(
    milestones: Optional[Sequence[str]], today: Optional[date] = None
) -> Dict[str, object]:
    """Build the phase schedule, aligned to customer milestones when possible.

    Returns a dict with ``source`` ("customer_milestones" | "standard_template"),
    ``phases`` (ordered windows with anchor attribution), parsing diagnostics
    (``unparsed_milestones``, ``unaligned_milestones``), ``conflicts``, a
    one-line ``summary``, and preformatted ``schedule_lines``.
    """
    today = today or date.today()
    parsed: List[ParsedMilestone] = []
    unparsed: List[str] = []
    for text in milestones or []:
        milestone = parse_milestone(text, today)
        if milestone is None:
            if str(text or "").strip():
                unparsed.append(str(text).strip())
        else:
            parsed.append(milestone)

    anchors: Dict[int, dict] = {}
    unaligned: List[dict] = []
    for milestone in parsed:
        if milestone.phase is None:
            unaligned.append(
                {"label": milestone.label, "window": milestone.display}
            )
            continue
        phase_index = PHASES.index(milestone.phase)
        anchors[phase_index] = _merge_anchor(anchors.get(phase_index), milestone)

    if not anchors:
        template = _standard_template()
        template["unparsed_milestones"] = unparsed
        template["unaligned_milestones"] = unaligned
        return template

    # Deadline anchors pin the phase to the END of the stated window (e.g.
    # "full migration next year" => cutover targeted for the end of next year).
    for anchor in anchors.values():
        if anchor["deadline"]:
            anchor["start"] = anchor["end"]

    # Out-of-order anchors are reported, not silently reordered.
    conflicts: List[str] = []
    anchored_indices = sorted(anchors)
    for first, second in zip(anchored_indices, anchored_indices[1:]):
        if anchors[second]["start"] < anchors[first]["start"]:
            conflicts.append(
                f"'{PHASES[second]}' ({' / '.join(anchors[second]['displays'])}) is "
                f"scheduled before '{PHASES[first]}' "
                f"({' / '.join(anchors[first]['displays'])}) — confirm sequencing "
                "with the customer."
            )

    # Assign month windows to every phase.
    windows: List[Optional[Tuple[int, int]]] = [None] * len(PHASES)
    for index, anchor in anchors.items():
        windows[index] = (anchor["start"], anchor["end"])

    first_anchor = anchored_indices[0]
    # Leading phases share the months between now and the first anchor.
    _fill_gap(windows, 0, first_anchor, start=0, end=windows[first_anchor][0])
    # Interior gaps between consecutive anchors.
    for first, second in zip(anchored_indices, anchored_indices[1:]):
        _fill_gap(
            windows,
            first + 1,
            second,
            start=windows[first][1] + 1,
            end=windows[second][0],
        )
    # Trailing phases get default durations after the last anchor.
    cursor = windows[anchored_indices[-1]][1] + 1
    for index in range(anchored_indices[-1] + 1, len(PHASES)):
        duration = _DEFAULT_PHASE_MONTHS[index]
        windows[index] = (cursor, cursor + duration - 1)
        cursor += duration

    phases = []
    for index, name in enumerate(PHASES):
        start, end = windows[index]
        anchor = anchors.get(index)
        anchored_to = None
        if anchor:
            joined = " / ".join(dict.fromkeys(anchor["displays"]))
            prefix = "by " if anchor["deadline"] else ""
            anchored_to = (
                f"customer milestone: {', '.join(dict.fromkeys(anchor['labels']))} "
                f"({prefix}{joined})"
            )
        phases.append(
            {
                "phase": name,
                "window": format_window(start, end, today),
                "start_month": start,
                "end_month": end,
                "anchored_to": anchored_to,
            }
        )

    cutover_window = phases[PHASES.index("Cutover")]["window"]
    summary = (
        f"Schedule aligned to {len(parsed)} customer milestone"
        f"{'s' if len(parsed) != 1 else ''}; cutover targeted for {cutover_window}."
    )
    if conflicts:
        summary += " Note: milestone sequencing conflicts were detected."

    return {
        "source": "customer_milestones",
        "phases": phases,
        "milestones_used": [
            {"label": m.label, "phase": m.phase, "window": m.display}
            for m in parsed
            if m.phase is not None
        ],
        "unparsed_milestones": unparsed,
        "unaligned_milestones": unaligned,
        "conflicts": conflicts,
        "summary": summary,
        "schedule_lines": [
            f"{p['phase']}: {p['window']}"
            + (f"  [{p['anchored_to']}]" if p["anchored_to"] else "")
            for p in phases
        ],
    }


def _fill_gap(
    windows: List[Optional[Tuple[int, int]]],
    first_phase: int,
    end_phase: int,
    *,
    start: int,
    end: int,
) -> None:
    """Distribute months [start, end) evenly across phases [first_phase, end_phase).

    When the gap is smaller than the number of phases, phases share boundary
    months (acceptable at planning granularity; the narrative refines to weeks).
    """
    count = end_phase - first_phase
    if count <= 0:
        return
    available = max(end - start, 0)
    base, remainder = divmod(available, count)
    cursor = start
    for offset in range(count):
        length = base + (1 if offset < remainder else 0)
        if length <= 0:  # zero-month gap -> pin to the preceding boundary month
            windows[first_phase + offset] = (max(cursor - 1, 0), max(cursor - 1, 0))
        else:
            windows[first_phase + offset] = (cursor, cursor + length - 1)
            cursor += length
