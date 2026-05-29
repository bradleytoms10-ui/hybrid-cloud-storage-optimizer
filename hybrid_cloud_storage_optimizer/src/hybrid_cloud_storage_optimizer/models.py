"""Typed data contracts passed between agents.

Using Pydantic models for the analysis handoff replaces fragile free-text/JSON
parsing: the storage analyst emits a validated ``StorageAnalysis`` and the cost
estimator receives structured, type-checked fields (notably the effective capacity
and protocol need that drive the cost calculation).
"""

from typing import List

from pydantic import BaseModel, Field


class StorageAnalysis(BaseModel):
    """Structured result of the on-prem storage analysis task."""

    summary: str = Field(..., description="Concise narrative summary of the environment.")
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
