"""Framework-free hybrid-cloud storage TCO engine.

This module contains the pure pricing/TCO logic with no dependency on CrewAI or
Pydantic, so it can be unit-tested in isolation and reused outside the agent. The
CrewAI tool wrapper lives in ``storage_cost_calculator.py``.

Methodology (defensible, documented assumptions)
-------------------------------------------------
* Sizing is done on EFFECTIVE capacity (post dedup/compression), never raw.
* TCO is summed MONTH-BY-MONTH over the horizon (default 3 years). Capacity grows
  at a monthly rate derived from the annual growth rate, so growth compounds
  correctly over time rather than being applied as a single flat multiplier.
* Monthly egress = (effective capacity) x (hot-data fraction) x (egress turnover)
  x (egress $/GB). ``egress_turnover`` is how many times the hot working set is
  read out of the cloud per month (default 1.0). This is an explicit assumption,
  not a hidden constant.
* A single storage tier (hot/standard) is priced per provider. Real deployments
  would tier the ~80% cold/archival data to cheaper classes (S3 Glacier, Blob
  Archive) or FabricPool, which would further lower object-storage TCO — see
  ``EXCLUDED_FROM_MODEL``.

Prices are public US-East list prices captured at ``PRICING_AS_OF`` and are
approximate; treat outputs as planning estimates, not quotes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

try:  # package import (production)
    from . import scoring
    from .scoring import CustomerContext
except ImportError:  # standalone import (isolated tests)
    import scoring
    from scoring import CustomerContext

GB_PER_TB = 1024
MONTHS_PER_YEAR = 12

PRICING_AS_OF = "2026-06"
PRICING_REGION = "US East"

OBJECT_STORAGE = "Object Storage"
NETAPP_MANAGED_FILE = "NetApp Managed File"

# Costs intentionally NOT modeled (documented for honesty / future work).
EXCLUDED_FROM_MODEL = (
    "API/request charges, data-retrieval and early-deletion fees, cold-tier "
    "(Glacier/Archive) and FabricPool tiering savings, snapshot/backup capacity, "
    "support plans, and inter-AZ traffic."
)


@dataclass(frozen=True)
class ProviderRate:
    """List-price rates for one storage target.

    ``throughput_per_mbps_month`` models provisioned-throughput cost for managed
    file services that decouple throughput from capacity (FSxN, CVO). It is a
    planning-grade approximation. Azure NetApp Files is left at 0 here because its
    throughput is bundled into the capacity-tier rate (Standard 16 / Premium 64 /
    Ultra 128 MiB/s per TiB); object storage has no provisioned throughput.
    """

    storage_per_gb_month: float
    egress_per_gb: float
    category: str
    throughput_per_mbps_month: float = 0.0


# Public US-East list prices, planning-grade (approximate; verified against
# provider pricing pages as of PRICING_AS_OF). Object-storage = hot/standard tier.
# NetApp-managed file rates assume production Multi-AZ deployments and vary with
# region, throughput/IOPS, and capacity-pool tiering.
#   AWS S3 Standard ............ $0.023/GB-mo (first 50 TB)
#   Azure Blob Hot (LRS) ....... $0.018/GB-mo
#   Google Cloud Standard ...... $0.020/GB-mo
#   FSx for NetApp ONTAP (SSD) . ~$0.045/GB-mo (Multi-AZ; single-AZ is lower)
#   Cloud Volumes ONTAP ........ ~$0.060/GB-mo (capacity-based, BYOL varies)
#   Azure NetApp Files Standard  ~$0.147/GiB-mo
# Throughput rates ($/MBps-month) are planning-grade approximations for providers
# that provision throughput separately (FSxN, CVO); confirm against the provider
# calculator for a quote. ANF/object are 0 (bundled / not provisioned).
PROVIDER_RATES: Dict[str, ProviderRate] = {
    "AWS_S3": ProviderRate(0.023, 0.09, OBJECT_STORAGE),
    "Azure_Blob": ProviderRate(0.018, 0.10, OBJECT_STORAGE),
    "Google_Cloud": ProviderRate(0.020, 0.08, OBJECT_STORAGE),
    "CVO": ProviderRate(0.060, 0.09, NETAPP_MANAGED_FILE, 0.90),
    "FSx_for_NetApp_ONTAP": ProviderRate(0.045, 0.09, NETAPP_MANAGED_FILE, 0.78),
    "Azure_NetApp_Files_Standard": ProviderRate(0.147, 0.10, NETAPP_MANAGED_FILE),
}

# Tokens that indicate a file-protocol (NFS/SMB) workload requiring a managed
# NetApp file service rather than object storage.
FILE_PROTOCOL_TOKENS = (
    "nfs",
    "smb",
    "cifs",
    "file share",
    "file protocol",
    "ontap",
)


def effective_capacity_tb(raw_or_used_tb: float, dedup_ratio: float) -> float:
    """Return capacity after dedup/compression. ``dedup_ratio`` of 2.0 == 2:1."""
    _require(raw_or_used_tb > 0, "capacity must be greater than 0 TB")
    _require(dedup_ratio >= 1, "dedup_ratio must be >= 1 (e.g. 2.0 for 2:1)")
    return raw_or_used_tb / dedup_ratio


def needs_file_protocol(workload_profile: str) -> bool:
    """True if the workload text implies an NFS/SMB file-protocol requirement."""
    text = (workload_profile or "").lower()
    return any(token in text for token in FILE_PROTOCOL_TOKENS)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


# FabricPool capacity tier: cold blocks tiered off a NetApp-managed performance
# tier land on low-cost object storage. We model that tier at the AWS S3 rate.
FABRICPOOL_CAPACITY_TIER_RATE = PROVIDER_RATES["AWS_S3"].storage_per_gb_month


def calculate_tco(
    effective_tb: float,
    hot_percent: float = 20.0,
    annual_growth_percent: float = 15.0,
    egress_turnover_per_month: float = 1.0,
    horizon_years: int = 3,
    enable_tiering: bool = True,
    capacity_tier_rate_per_gb: float = FABRICPOOL_CAPACITY_TIER_RATE,
    provisioned_throughput_mbps: float = 0.0,
) -> Dict[str, Dict[str, float]]:
    """Compute per-provider TCO over the horizon, compounding growth monthly.

    Args:
        effective_tb: Effective (post-dedup) capacity in TB.
        hot_percent: Percent of data frequently accessed (drives egress). 0-100.
        annual_growth_percent: Expected annual capacity growth, percent. >= 0.
        egress_turnover_per_month: Times the hot set is read out per month. >= 0.
        horizon_years: TCO horizon in whole years. >= 1.
        enable_tiering: When True, NetApp-managed targets use FabricPool tiering —
            hot data stays on the managed rate and cold data is tiered to the
            object-storage capacity tier. Object-storage targets are unaffected.
        capacity_tier_rate_per_gb: $/GB-month for the FabricPool capacity tier.
        provisioned_throughput_mbps: Sustained throughput to provision (MBps).
            Adds a monthly throughput cost for providers that bill throughput
            separately (FSxN, CVO). 0 disables (default), preserving prior numbers.

    Returns:
        Mapping of provider -> cost breakdown (initial monthly figures, blended
        effective storage rate, and total TCO over the horizon).
    """
    _require(effective_tb > 0, "effective_tb must be greater than 0")
    _require(0 <= hot_percent <= 100, "hot_percent must be between 0 and 100")
    _require(annual_growth_percent >= 0, "annual_growth_percent must be >= 0")
    _require(egress_turnover_per_month >= 0, "egress_turnover_per_month must be >= 0")
    _require(horizon_years >= 1, "horizon_years must be >= 1")
    _require(capacity_tier_rate_per_gb > 0, "capacity_tier_rate_per_gb must be > 0")
    _require(
        provisioned_throughput_mbps >= 0, "provisioned_throughput_mbps must be >= 0"
    )

    months = horizon_years * MONTHS_PER_YEAR
    monthly_growth = (1 + annual_growth_percent / 100) ** (1 / MONTHS_PER_YEAR)
    hot_fraction = hot_percent / 100
    cold_fraction = 1 - hot_fraction

    results: Dict[str, Dict[str, float]] = {}
    for provider, rate in PROVIDER_RATES.items():
        tiered = enable_tiering and rate.category == NETAPP_MANAGED_FILE
        if tiered:
            # Blended rate: hot stays on the managed tier, cold tiers to object.
            effective_rate = (
                hot_fraction * rate.storage_per_gb_month
                + cold_fraction * capacity_tier_rate_per_gb
            )
        else:
            effective_rate = rate.storage_per_gb_month

        # Provisioned-throughput cost (flat monthly; 0 for object/ANF/no-throughput).
        monthly_throughput = (
            rate.throughput_per_mbps_month * provisioned_throughput_mbps
        )

        total_storage = 0.0
        total_egress = 0.0
        initial_storage = 0.0
        initial_egress = 0.0

        for month in range(months):
            capacity_gb = effective_tb * GB_PER_TB * (monthly_growth**month)
            storage_cost = capacity_gb * effective_rate
            egress_cost = (
                capacity_gb
                * hot_fraction
                * egress_turnover_per_month
                * rate.egress_per_gb
            )
            total_storage += storage_cost
            total_egress += egress_cost
            if month == 0:
                initial_storage = storage_cost
                initial_egress = egress_cost

        total_throughput = monthly_throughput * months
        results[provider] = {
            "category": rate.category,
            "list_storage_rate_per_gb": rate.storage_per_gb_month,
            "effective_storage_rate_per_gb": round(effective_rate, 5),
            "fabricpool_tiering_applied": tiered,
            "initial_monthly_storage_usd": round(initial_storage, 2),
            "initial_monthly_egress_usd": round(initial_egress, 2),
            "initial_monthly_throughput_usd": round(monthly_throughput, 2),
            "initial_monthly_total_usd": round(
                initial_storage + initial_egress + monthly_throughput, 2
            ),
            "horizon_tco_usd": round(
                total_storage + total_egress + total_throughput, 2
            ),
        }
    return results


def recommend(
    results: Dict[str, Dict[str, float]], file_protocol_required: bool
) -> Dict[str, str]:
    """Pick a provider: cheapest managed-file option if NFS/SMB is required,
    otherwise the lowest-TCO option overall."""
    if file_protocol_required:
        candidates = {
            p: v for p, v in results.items() if v["category"] == NETAPP_MANAGED_FILE
        }
        reason = (
            "Workload requires NFS/SMB file-protocol access; NetApp-managed file "
            "services preserve ONTAP semantics (snapshots, SnapMirror, dedup). "
            "Selected the lowest-TCO managed option."
        )
    else:
        candidates = results
        reason = "Lowest 3-year TCO for an object-storage-compatible workload."

    best = min(candidates, key=lambda p: candidates[p]["horizon_tco_usd"])
    return {
        "recommended_provider": best.replace("_", " "),
        "recommended_provider_key": best,
        "reason": reason,
    }


def build_report(
    raw_or_used_tb: float,
    dedup_ratio: float = 2.0,
    hot_percent: float = 20.0,
    annual_growth_percent: float = 15.0,
    egress_turnover_per_month: float = 1.0,
    horizon_years: int = 3,
    workload_profile: str = "",
    file_protocol_required: Optional[bool] = None,
    enable_tiering: bool = True,
    context: Optional[CustomerContext] = None,
    provisioned_throughput_mbps: float = 0.0,
    on_prem_annual_usd: float = 0.0,
    target_reduction_percent: float = 30.0,
) -> Dict[str, object]:
    """End-to-end: derive effective capacity, compute TCO, score, and recommend.

    ``file_protocol_required`` is authoritative when provided (e.g. passed from the
    upstream StorageAnalysis). When ``None``, it is inferred from ``workload_profile``
    keywords as a fallback. ``enable_tiering`` applies FabricPool cold-tiering to
    NetApp-managed targets (default on). ``context`` is the Solutions-Engineer
    discovery context; when provided it drives a multi-factor ranking so the
    recommendation reflects cloud affinity, performance, compliance, licensing, and
    strategy — not just cost. ``provisioned_throughput_mbps`` adds performance cost
    for throughput-billed services. ``on_prem_annual_usd`` is the customer's current
    annual storage spend; when > 0 a business case (% TCO reduction vs the
    ``target_reduction_percent`` goal) is computed. Cost figures remain authoritative.
    """
    eff = effective_capacity_tb(raw_or_used_tb, dedup_ratio)
    costs = calculate_tco(
        effective_tb=eff,
        hot_percent=hot_percent,
        annual_growth_percent=annual_growth_percent,
        egress_turnover_per_month=egress_turnover_per_month,
        horizon_years=horizon_years,
        enable_tiering=enable_tiering,
        provisioned_throughput_mbps=provisioned_throughput_mbps,
    )
    file_required = (
        file_protocol_required
        if file_protocol_required is not None
        else needs_file_protocol(workload_profile)
    )
    ranked = scoring.score_options(
        costs, needs_file_protocol=file_required, context=context
    )
    top = ranked[0]
    rec = {
        "recommended_provider": top["provider"],
        "recommended_provider_key": top["provider_key"],
        "reason": _explain(top, file_required),
    }
    recommended_tco = costs[rec["recommended_provider_key"]]["horizon_tco_usd"]
    business_case = _business_case(
        recommended_tco, horizon_years, on_prem_annual_usd, target_reduction_percent
    )

    return {
        "effective_capacity_after_dedup_tb": round(eff, 2),
        "horizon_years": horizon_years,
        "needs_file_protocol": file_required,
        "assumptions": {
            "pricing_as_of": PRICING_AS_OF,
            "region": PRICING_REGION,
            "hot_percent": hot_percent,
            "annual_growth_percent": annual_growth_percent,
            "egress_turnover_per_month": egress_turnover_per_month,
            "provisioned_throughput_mbps": provisioned_throughput_mbps,
            "fabricpool_tiering_enabled": enable_tiering,
            "fabricpool_capacity_tier_rate_per_gb": FABRICPOOL_CAPACITY_TIER_RATE,
            "excluded_from_model": EXCLUDED_FROM_MODEL,
        },
        "costs": costs,
        "ranked_options": ranked,
        "recommended_provider": rec["recommended_provider"],
        "three_year_tco_recommended_usd": recommended_tco,
        "business_case": business_case,
        "reason": rec["reason"],
        "note": (
            "NetApp-managed options preserve NFS/SMB and ONTAP features. With "
            "FabricPool tiering enabled, cold data is tiered to low-cost object "
            "storage, substantially lowering managed-file TCO versus keeping all "
            "data on the performance tier. Ranking reflects the supplied customer "
            "context; cost figures are authoritative."
        ),
    }


def _explain(option: Dict[str, object], file_required: bool) -> str:
    """Build a one-paragraph rationale for the top-ranked option."""
    notes = option.get("rationale") or []
    factors = "; ".join(notes) if notes else "lowest blended cost-and-fit score"
    tco = option["horizon_tco_usd"]
    return (
        f"{option['provider']} ranks highest (score {option['total_score']}/100, "
        f"3-yr TCO ${tco:,.0f}). Key factors: {factors}."
    )


def _business_case(
    recommended_tco: float,
    horizon_years: int,
    on_prem_annual_usd: float,
    target_reduction_percent: float,
) -> Dict[str, object]:
    """Build the TCO-reduction business case vs the customer's current spend.

    Without a supplied baseline we cannot claim a reduction — say so explicitly
    rather than imply savings (a common credibility failure in SE deliverables).
    """
    recommended_annual = recommended_tco / horizon_years
    if on_prem_annual_usd <= 0:
        return {
            "baseline_provided": False,
            "recommended_annual_usd": round(recommended_annual, 2),
            "target_reduction_percent": target_reduction_percent,
            "summary": (
                "No current on-prem annual spend was provided, so a % TCO reduction "
                "cannot be computed. Capture the customer's current annual storage "
                f"cost to validate the {target_reduction_percent:.0f}% reduction goal. "
                f"Recommended cloud run-rate is ~${recommended_annual:,.0f}/yr."
            ),
        }
    baseline_horizon = on_prem_annual_usd * horizon_years
    reduction_pct = (baseline_horizon - recommended_tco) / baseline_horizon * 100
    meets = reduction_pct >= target_reduction_percent
    verb = "meets" if meets else "falls short of"
    return {
        "baseline_provided": True,
        "on_prem_annual_usd": round(on_prem_annual_usd, 2),
        "on_prem_horizon_usd": round(baseline_horizon, 2),
        "recommended_annual_usd": round(recommended_annual, 2),
        "tco_reduction_percent": round(reduction_pct, 1),
        "target_reduction_percent": target_reduction_percent,
        "meets_target": meets,
        "summary": (
            f"Recommended {horizon_years}-yr TCO ${recommended_tco:,.0f} vs current "
            f"${baseline_horizon:,.0f} (${on_prem_annual_usd:,.0f}/yr) is a "
            f"{reduction_pct:.0f}% reduction, which {verb} the "
            f"{target_reduction_percent:.0f}% target."
        ),
    }


def provider_table() -> List[str]:
    """Convenience: provider keys in stable order (for display/tests)."""
    return list(PROVIDER_RATES.keys())
