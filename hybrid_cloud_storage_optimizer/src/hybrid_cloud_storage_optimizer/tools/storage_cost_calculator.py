"""CrewAI tool wrapper around the framework-free pricing engine (``pricing.py``).

Keeping the math in ``pricing.py`` makes it unit-testable without CrewAI; this
module only handles the agent-facing schema, input validation, and error framing.
"""

import json
from typing import Any, Dict, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from . import pricing, scoring


class StorageCostCalculatorInput(BaseModel):
    """Validated inputs for the storage cost calculator."""

    capacity_tb: float = Field(
        ...,
        gt=0,
        description="Capacity in TB to price. Pass the effective (post-dedup) "
        "capacity and leave dedup_ratio at 1.0, or pass used capacity with the "
        "real dedup_ratio.",
    )
    dedup_ratio: float = Field(
        1.0,
        ge=1,
        description="Dedup/compression ratio (e.g. 2.0 for 2:1). Use 1.0 if "
        "capacity_tb is already post-dedup.",
    )
    hot_percent: float = Field(
        20.0, ge=0, le=100, description="Percent of data frequently accessed (hot)."
    )
    growth_rate_percent: float = Field(
        15.0, ge=0, description="Expected annual capacity growth rate, percent."
    )
    needs_file_protocol: Optional[bool] = Field(
        None,
        description="Whether the workload requires NFS/SMB/CIFS file-protocol "
        "access. Pass the value from the upstream StorageAnalysis. This is "
        "authoritative; when omitted, it is inferred from workload_profile text.",
    )
    enable_tiering: bool = Field(
        True,
        description="Apply NetApp FabricPool cold-tiering to managed-file targets "
        "(cold data tiered to low-cost object storage). Default true.",
    )
    workload_profile: str = Field(
        "",
        description="The original workload description text. Used only as a "
        "fallback to detect file-protocol need when needs_file_protocol is omitted.",
    )
    context_json: str = Field(
        "",
        description="Optional JSON string of customer context that re-ranks the "
        'recommendation, e.g. {"cloud_provider":"azure","performance_tier":"high",'
        '"budget_sensitivity":"performance","existing_netapp_ela":true,'
        '"cloud_exit_optionality":false,"compliance":["fedramp"]}. Pass it through '
        "verbatim from the customer_context_json input; do not invent values.",
    )


class StorageCostCalculatorTool(BaseTool):
    name: str = "storage_cost_calculator"
    description: str = (
        "Deterministic 2026 hybrid-cloud TCO calculator across 6 providers (AWS S3, "
        "Azure Blob, Google Cloud, CVO, FSx for NetApp ONTAP, Azure NetApp Files). "
        "Sizes on effective (post-dedup) capacity, compounds growth month-by-month, "
        "and recommends NetApp-managed file services when NFS/SMB compatibility is "
        "needed, otherwise the lowest-TCO option."
    )
    args_schema: Type[BaseModel] = StorageCostCalculatorInput

    def _run(
        self,
        capacity_tb: float,
        dedup_ratio: float = 1.0,
        hot_percent: float = 20.0,
        growth_rate_percent: float = 15.0,
        needs_file_protocol: Optional[bool] = None,
        enable_tiering: bool = True,
        workload_profile: str = "",
        context_json: str = "",
    ) -> Dict[str, Any]:
        context = None
        if context_json:
            try:
                context = scoring.context_from_dict(json.loads(context_json))
            except (ValueError, TypeError):
                context = None  # tolerate malformed JSON -> neutral ranking
        try:
            return pricing.build_report(
                raw_or_used_tb=capacity_tb,
                dedup_ratio=dedup_ratio,
                hot_percent=hot_percent,
                annual_growth_percent=growth_rate_percent,
                workload_profile=workload_profile,
                file_protocol_required=needs_file_protocol,
                enable_tiering=enable_tiering,
                context=context,
            )
        except ValueError as exc:
            return {"error": f"Invalid input to storage_cost_calculator: {exc}"}
