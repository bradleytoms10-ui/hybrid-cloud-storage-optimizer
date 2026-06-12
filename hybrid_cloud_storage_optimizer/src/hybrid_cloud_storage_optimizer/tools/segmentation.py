"""Workload segmentation: model an estate as typed segments, not one blended pool.

Real environments are rarely uniform: an Oracle/SAP SAN slice (iSCSI/FC LUNs), an
NFS/SMB file-services slice, and a cold archive slice have different protocol
constraints, access patterns, and therefore different optimal landing zones. This
module is the framework-free data layer for that: a ``Segment`` value object plus
a tolerant normalizer that accepts loosely-typed dicts (from the LLM analyst or
the UI) and returns validated segments the pricing engine can price per-slice.

Design notes
------------
* Segment capacities are EFFECTIVE (post dedup/compression) TB, consistent with
  the engine's sizing philosophy. The storage analyst applies per-workload dedup
  expectations (e.g. databases ~1.5:1, general file ~2:1) before handing off.
* Normalization is tolerant by design (LLM/UI input): unknown workload-type
  tokens are coerced via keyword mapping, invalid entries are dropped (never
  raise mid-pipeline), and missing hot/growth fall back to documented defaults.
* No imports from the rest of the package, so it unit-tests standalone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

# Canonical workload types.
FILE = "file"  # NFS/SMB/CIFS file services
BLOCK = "block"  # SAN: iSCSI/FC LUNs (databases, VMware datastores)
OBJECT = "object"  # archive/backup/cold data, object-API friendly

WORKLOAD_TYPES = (FILE, BLOCK, OBJECT)

# Tokens used to coerce free-form type labels into canonical types. Checked in
# order; first match wins. Substring match against the lowercased label.
_TYPE_TOKENS: Sequence[tuple[str, str]] = (
    ("block", BLOCK),
    ("san", BLOCK),
    ("iscsi", BLOCK),
    ("fc", BLOCK),
    ("lun", BLOCK),
    ("oracle", BLOCK),
    ("sap", BLOCK),
    ("database", BLOCK),
    ("vmware", BLOCK),
    ("datastore", BLOCK),
    ("file", FILE),
    ("nfs", FILE),
    ("smb", FILE),
    ("cifs", FILE),
    ("nas", FILE),
    ("home", FILE),
    ("object", OBJECT),
    ("archive", OBJECT),
    ("backup", OBJECT),
    ("cold", OBJECT),
    ("s3", OBJECT),
    ("blob", OBJECT),
    ("retention", OBJECT),
)

# Archive/cold segments default to a low-but-nonzero hot fraction (restores and
# audits still read data out). File/block segments inherit the blended default.
ARCHIVE_DEFAULT_HOT_PERCENT = 5.0


@dataclass(frozen=True)
class Segment:
    """One workload slice of the estate (validated, canonical form)."""

    name: str
    workload_type: str  # one of WORKLOAD_TYPES
    capacity_tb: float  # EFFECTIVE (post-dedup) TB
    hot_percent: float
    growth_rate_percent: float


def coerce_workload_type(label: object) -> Optional[str]:
    """Map a free-form type label to a canonical workload type (None if unknown)."""
    text = str(label or "").strip().lower()
    if not text:
        return None
    if text in WORKLOAD_TYPES:
        return text
    for token, canonical in _TYPE_TOKENS:
        if token in text:
            return canonical
    return None


def _as_float(value: object) -> Optional[float]:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result


def normalize_segments(
    raw_segments: Optional[Iterable[Dict[str, object]]],
    *,
    default_hot_percent: float = 20.0,
    default_growth_percent: float = 15.0,
) -> List[Segment]:
    """Validate and canonicalize loosely-typed segment dicts.

    Tolerant by design: entries with an unrecognizable type or a non-positive
    capacity are silently dropped (the caller falls back to blended pricing when
    nothing survives). Hot %/growth use the supplied value when sane, otherwise
    the blended defaults (archive segments default to a low hot fraction).
    """
    segments: List[Segment] = []
    for index, item in enumerate(raw_segments or []):
        if not isinstance(item, dict):
            continue
        workload_type = coerce_workload_type(
            item.get("workload_type") or item.get("type")
        )
        capacity = _as_float(item.get("capacity_tb"))
        if workload_type is None or capacity is None or capacity <= 0:
            continue

        hot = _as_float(item.get("hot_data_percent", item.get("hot_percent")))
        if hot is None or not (0 <= hot <= 100):
            hot = (
                ARCHIVE_DEFAULT_HOT_PERCENT
                if workload_type == OBJECT
                else default_hot_percent
            )

        growth = _as_float(
            item.get("growth_rate_percent", item.get("annual_growth_percent"))
        )
        if growth is None or growth < 0:
            growth = default_growth_percent

        name = str(item.get("name") or "").strip() or f"Segment {index + 1}"
        segments.append(
            Segment(
                name=name,
                workload_type=workload_type,
                capacity_tb=round(capacity, 2),
                hot_percent=hot,
                growth_rate_percent=growth,
            )
        )
    return segments


def total_capacity_tb(segments: Sequence[Segment]) -> float:
    """Sum of effective segment capacities."""
    return round(sum(s.capacity_tb for s in segments), 2)


def describe(segment: Segment) -> str:
    """One-line human-readable description (used in assumptions/notes)."""
    return (
        f"{segment.name}: {segment.workload_type}, "
        f"{segment.capacity_tb:g} TB effective, "
        f"{segment.hot_percent:g}% hot, "
        f"{segment.growth_rate_percent:g}%/yr growth"
    )
