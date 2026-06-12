"""Framework-free, multi-factor recommendation scoring.

The original recommendation logic was binary — "if NFS/SMB, pick the cheapest
managed-file option" — which made FSx for NetApp ONTAP a near-universal answer.
Updates include weighing many dimensions and presents a *ranked* shortlist
with trade-offs. This module scores every provider on a transparent, documented
rubric so the ranking is explainable and testable (no LLM hand-waving). Dollar
costs remain authoritative from ``pricing.py``; scoring only re-ranks fit.

Score (0-100) = w_cost * cost_score + w_fit * fit_score
  - cost_score: min-max normalized 3-year TCO (cheapest = 100).
  - fit_score: 50 baseline + documented adjustments for the customer's context.
  - weights shift with budget_sensitivity (cost vs. performance priority).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

# Categories (kept in sync with pricing.py values).
OBJECT_STORAGE = "Object Storage"
NETAPP_MANAGED_FILE = "NetApp Managed File"


@dataclass(frozen=True)
class ProviderProfile:
    """Static, non-cost attributes used for fit scoring.

    ``serves_block_protocol`` is native SAN support (iSCSI/FC LUNs): true for
    FSx for NetApp ONTAP (iSCSI/NVMe-over-TCP) and Cloud Volumes ONTAP (iSCSI);
    false for Azure NetApp Files (NFS/SMB only — Azure's block answer is a
    different product) and for all object storage.
    """

    cloud: str  # "aws" | "azure" | "gcp" | "any"
    serves_file_protocol: bool  # native NFS/SMB
    portability: str  # "high" | "medium" | "low"
    netapp_managed: bool
    serves_block_protocol: bool = False  # native iSCSI/FC (SAN)


PROVIDER_PROFILES: Dict[str, ProviderProfile] = {
    "AWS_S3": ProviderProfile("aws", False, "low", False, False),
    "Azure_Blob": ProviderProfile("azure", False, "low", False, False),
    "Google_Cloud": ProviderProfile("gcp", False, "low", False, False),
    "CVO": ProviderProfile("any", True, "high", True, True),
    "FSx_for_NetApp_ONTAP": ProviderProfile("aws", True, "medium", True, True),
    "Azure_NetApp_Files_Standard": ProviderProfile(
        "azure", True, "medium", True, False
    ),
}

# Weight presets: (cost_weight, fit_weight).
_WEIGHTS = {
    "cost": (0.7, 0.3),
    "balanced": (0.5, 0.5),
    "performance": (0.3, 0.7),
}


@dataclass(frozen=True)
class CustomerContext:
    """Solutions-Engineer discovery context that shapes the ranking.

    All fields optional; an empty context falls back to cost + protocol fit.
    """

    cloud_provider: str = ""  # "aws" | "azure" | "gcp" | "multi" | ""
    performance_tier: str = "standard"  # "high" | "standard" | "archive"
    budget_sensitivity: str = "balanced"  # "cost" | "balanced" | "performance"
    existing_netapp_ela: bool = False  # BYOL/ELA favors CVO
    cloud_exit_optionality: bool = False  # portability favors CVO
    compliance: Sequence[str] = field(default_factory=tuple)  # e.g. ("fedramp",)


_VALID_CLOUDS = {"aws", "azure", "gcp", "multi", ""}
_VALID_PERF = {"high", "standard", "archive"}
_VALID_BUDGET = {"cost", "balanced", "performance"}


def context_from_dict(data: dict) -> CustomerContext:
    """Build a CustomerContext from an arbitrary dict, ignoring unknown keys and
    coercing invalid values to safe defaults. Tolerant by design (LLM/UI input)."""
    data = data or {}

    def _str(key: str, default: str, valid: set) -> str:
        val = str(data.get(key, default) or default).strip().lower()
        return val if val in valid else default

    compliance = data.get("compliance") or []
    if isinstance(compliance, str):
        compliance = [c.strip() for c in compliance.split(",") if c.strip()]

    return CustomerContext(
        cloud_provider=_str("cloud_provider", "", _VALID_CLOUDS),
        performance_tier=_str("performance_tier", "standard", _VALID_PERF),
        budget_sensitivity=_str("budget_sensitivity", "balanced", _VALID_BUDGET),
        existing_netapp_ela=bool(data.get("existing_netapp_ela", False)),
        cloud_exit_optionality=bool(data.get("cloud_exit_optionality", False)),
        compliance=tuple(str(c).strip().lower() for c in compliance),
    )


def _fit_score(
    provider: str,
    profile: ProviderProfile,
    ctx: CustomerContext,
    needs_file_protocol: bool,
    needs_block_protocol: bool = False,
) -> tuple[float, List[str]]:
    """Return (clamped 0-100 fit score, list of human-readable rationale notes)."""
    score = 50.0
    notes: List[str] = []

    # Protocol requirement is the strongest signal.
    if needs_file_protocol:
        if profile.serves_file_protocol:
            score += 10
            notes.append("serves NFS/SMB natively")
        else:
            score -= 40
            notes.append("cannot natively serve the required file protocol")

    if needs_block_protocol:
        if profile.serves_block_protocol:
            score += 10
            notes.append("serves iSCSI/block (SAN) natively")
        else:
            score -= 40
            notes.append("cannot natively serve block (iSCSI/FC) workloads")

    # Cloud affinity with the customer's existing footprint.
    cloud = ctx.cloud_provider.lower()
    if cloud in ("aws", "azure", "gcp"):
        if profile.cloud == cloud:
            score += 25
            notes.append(f"native to the customer's {cloud.upper()} footprint")
        elif profile.cloud == "any":
            score += 10
            notes.append("cloud-agnostic, deploys into any footprint")
        else:
            score -= 15
            notes.append(f"not native to {cloud.upper()}")
    elif cloud == "multi":
        if profile.portability == "high":
            score += 20
            notes.append("high portability for multi-cloud strategy")

    # Performance posture.
    if ctx.performance_tier == "high":
        if profile.netapp_managed:
            score += 15
            notes.append("low-latency managed file performance")
        else:
            score -= 20
            notes.append("object storage ill-suited to high-performance needs")
    elif ctx.performance_tier == "archive":
        if not profile.netapp_managed:
            score += 15
            notes.append("cost-efficient for archival/cold data")
        else:
            score -= 10
            notes.append("premium tier is overkill for archival data")

    # Commercial: existing NetApp ELA/BYOL favors CVO.
    if ctx.existing_netapp_ela and provider == "CVO":
        score += 20
        notes.append("leverages existing NetApp ELA/BYOL licensing")

    # Strategic: cloud-exit optionality rewards portability.
    if ctx.cloud_exit_optionality:
        if profile.portability == "high":
            score += 20
            notes.append("preserves cloud-exit optionality")
        elif profile.netapp_managed:
            score -= 5

    # Compliance maturity (NetApp-managed services have strong gov/compliance story).
    if ctx.compliance:
        regimes = ", ".join(ctx.compliance)
        if profile.netapp_managed:
            score += 10
            notes.append(f"mature compliance posture for {regimes}")
        else:
            score += 5

    return max(0.0, min(100.0, score)), notes


def score_options(
    costs: Dict[str, Dict[str, float]],
    *,
    needs_file_protocol: bool,
    needs_block_protocol: bool = False,
    context: CustomerContext | None = None,
) -> List[Dict[str, object]]:
    """Rank providers by blended cost + fit score; return richest-first list."""
    ctx = context or CustomerContext()
    weights = _WEIGHTS.get(ctx.budget_sensitivity, _WEIGHTS["balanced"])
    w_cost, w_fit = weights

    tcos = {p: c["horizon_tco_usd"] for p, c in costs.items()}
    lo, hi = min(tcos.values()), max(tcos.values())
    span = hi - lo

    named_cloud = ctx.cloud_provider.lower() in ("aws", "azure", "gcp")

    ranked: List[Dict[str, object]] = []
    for provider, cost in costs.items():
        profile = PROVIDER_PROFILES[provider]
        # Cheapest = 100; most expensive = 0. Degenerate span -> neutral 50.
        cost_score = 100.0 if span == 0 else 100.0 * (hi - tcos[provider]) / span
        fit_score, notes = _fit_score(
            provider, profile, ctx, needs_file_protocol, needs_block_protocol
        )
        total = round(w_cost * cost_score + w_fit * fit_score, 1)

        # Three hard constraints decide whether an option can be the #1 pick:
        #   (1) file protocol: object storage can't natively serve required NFS/SMB;
        #   (2) block protocol: only SAN-capable services (FSxN, CVO) can serve
        #       iSCSI/FC LUN workloads — object storage and ANF cannot;
        #   (3) cloud fit: a service native to a *different* named cloud isn't
        #       deployable in that footprint (FSxN is AWS-only, ANF Azure-only).
        # Cloud-agnostic services (profile.cloud == "any", e.g. CVO) always fit.
        protocol_ok = (not needs_file_protocol) or profile.serves_file_protocol
        block_ok = (not needs_block_protocol) or profile.serves_block_protocol
        cloud_ok = (
            (not named_cloud)
            or profile.cloud == "any"
            or profile.cloud == ctx.cloud_provider.lower()
        )
        ineligible_reason = ""
        if not cloud_ok:
            ineligible_reason = f"not available in the customer's {ctx.cloud_provider.upper()} footprint"
        elif not protocol_ok:
            ineligible_reason = "cannot natively serve the required file protocol"
        elif not block_ok:
            ineligible_reason = "cannot natively serve block (iSCSI/FC) workloads"

        ranked.append(
            {
                "provider": provider.replace("_", " "),
                "provider_key": provider,
                "category": cost["category"],
                "horizon_tco_usd": cost["horizon_tco_usd"],
                "cost_score": round(cost_score, 1),
                "fit_score": round(fit_score, 1),
                "total_score": total,
                "eligible": protocol_ok and block_ok and cloud_ok,
                "ineligible_reason": ineligible_reason,
                "rationale": notes,
            }
        )

    # Eligible options first, then by blended score. Guarantees the top pick can
    # actually serve the workload AND deploy in the customer's cloud, even when an
    # ineligible option scores higher on raw cost.
    ranked.sort(key=lambda r: (r["eligible"], r["total_score"]), reverse=True)
    return ranked
