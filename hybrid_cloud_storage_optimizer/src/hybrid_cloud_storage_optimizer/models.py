"""Typed data contracts passed between agents.

Using Pydantic models for the analysis handoff replaces fragile free-text/JSON
parsing: the storage analyst emits a validated ``StorageAnalysis`` and the cost
estimator receives structured, type-checked fields (notably the effective capacity
and protocol need that drive the cost calculation).
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class WorkloadSegment(BaseModel):
    """One distinct workload slice of the estate (SAN/file/archive).

    Real environments are rarely one blended pool: an Oracle/SAP SAN slice
    (iSCSI/FC LUNs), an NFS/SMB file-services slice, and a cold archive slice
    have different protocol constraints and access patterns, so each is priced
    and placed separately by the cost engine.
    """

    name: str = Field(
        ...,
        description="Short descriptive name, e.g. 'Oracle SAN' or 'File services'.",
    )
    workload_type: str = Field(
        ...,
        description="'block' for SAN/iSCSI/FC/LUN workloads (databases, VMware), "
        "'file' for NFS/SMB/CIFS shares, 'object' for archive/backup/cold data.",
    )
    capacity_tb: float = Field(
        ...,
        description="EFFECTIVE (post-dedup/compression) capacity of this segment "
        "in TB. Apply a workload-appropriate dedup expectation (databases often "
        "~1.5:1, general file ~2:1). Segment capacities should sum to "
        "effective_capacity_tb.",
    )
    hot_data_percent: Optional[float] = Field(
        None,
        description="Hot/frequently-accessed percent for THIS segment, only if "
        "the input states it; otherwise leave null and the engine applies "
        "defaults (archive segments default low).",
    )
    growth_rate_percent: Optional[float] = Field(
        None,
        description="Annual growth percent for THIS segment, only if stated; "
        "otherwise leave null.",
    )


class StorageAnalysis(BaseModel):
    """Structured result of the on-prem storage analysis task."""

    summary: str = Field(
        ..., description="Concise narrative summary of the environment."
    )
    raw_capacity_tb: float = Field(..., description="Total raw capacity in TB.")
    used_capacity_tb: float = Field(
        ..., description="Used capacity in TB before deduplication."
    )
    dedup_ratio: float = Field(
        2.0, description="Deduplication/compression ratio, e.g. 2.0 for 2:1."
    )
    effective_capacity_tb: float = Field(
        ...,
        description="Effective capacity after dedup (used_capacity_tb / dedup_ratio). "
        "This is the value passed to the cost calculator as capacity_tb.",
    )
    hot_data_percent: float = Field(
        20.0, description="Percentage of data that is frequently accessed (hot)."
    )
    growth_rate_percent: float = Field(
        15.0, description="Expected annual capacity growth rate, percent."
    )
    needs_file_protocol: bool = Field(
        ...,
        description="True if the workload requires NFS/SMB/CIFS file-protocol access, "
        "which mandates a NetApp-managed file service over object storage.",
    )
    inefficiencies: List[str] = Field(
        default_factory=list, description="Identified inefficiencies or risks."
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Optimization or migration recommendations."
    )
    segments: List[WorkloadSegment] = Field(
        default_factory=list,
        description="Distinct workload segments, ONLY when the input clearly "
        "describes more than one workload class (e.g. SAN/iSCSI/FC/LUN/Oracle/"
        "SAP/VMware => block; NFS/SMB/CIFS/home directories => file; archive/"
        "backup/cold/retention => object). Leave empty for a uniform estate — "
        "never invent a split the input does not support.",
    )


class CustomerContext(BaseModel):
    """Structured Solutions-Engineer discovery context.

    Produced by the discovery agent from free-form input + uploaded artifacts +
    any explicit UI hints. Serialized to JSON and passed to the cost calculator,
    where it drives the multi-factor recommendation ranking.
    """

    cloud_provider: str = Field(
        "",
        description="Primary cloud footprint: 'aws', 'azure', 'gcp', 'multi', or "
        "'' if unknown. Infer from mentions of the provider in the input.",
    )
    performance_tier: str = Field(
        "standard",
        description="'high' (latency-sensitive), 'standard', or 'archive' (cold).",
    )
    budget_sensitivity: str = Field(
        "balanced",
        description="'cost', 'balanced', or 'performance' — the customer's priority.",
    )
    existing_netapp_ela: bool = Field(
        False,
        description="True if the customer has an existing NetApp ELA/BYOL licensing.",
    )
    cloud_exit_optionality: bool = Field(
        False,
        description="True if multi-cloud portability / cloud-exit flexibility matters.",
    )
    compliance: List[str] = Field(
        default_factory=list,
        description="Compliance regimes mentioned, e.g. ['fedramp', 'hipaa'].",
    )
    provisioned_throughput_mbps: float = Field(
        0.0,
        description="Sustained throughput to provision (MBps). Copy through from the "
        "hints verbatim; 0 if not specified. Drives performance cost.",
    )
    on_prem_annual_usd: float = Field(
        0.0,
        description="Customer's current on-prem annual storage spend (USD). Copy "
        "through from the hints verbatim; 0 if unknown. Drives the % TCO-reduction "
        "business case.",
    )
    milestones: List[str] = Field(
        default_factory=list,
        description="Customer-stated migration milestones, each formatted "
        "'Label — period', e.g. 'Discovery — Q3 2026', 'Pilot — Q4 2026', "
        "'Cutover — by March 2027'. Include every explicit hint verbatim and add "
        "milestones clearly stated in the notes/artifacts (phrases like 'pilot "
        "by Q4' or 'complete the migration in H1 2027'). Empty if none stated — "
        "do not invent dates.",
    )
