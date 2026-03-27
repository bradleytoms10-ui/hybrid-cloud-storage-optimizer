from crewai.tools import BaseTool
from typing import Dict, Any


class StorageCostCalculatorTool(BaseTool):
    name: str = "storage_cost_calculator"
    description: str = """
    Smart 2026 TCO calculator that considers both cost AND technical requirements.
    Automatically prefers NetApp-managed file services (CVO, FSxN, ANF) when NFS/SMB
    protocol compatibility is needed. Otherwise picks the cheapest object storage.
    """

    def _run(
        self,
        capacity_tb: float,
        dedup_ratio: float = 2.0,
        hot_percent: float = 20.0,
        growth_rate_percent: float = 15.0,
        workload_profile: str = "",
    ) -> Dict[str, Any]:

        effective_tb = capacity_tb / dedup_ratio
        growth_factor = (1 + growth_rate_percent / 100) ** 3

        # Realistic March 2026 pricing (US East)
        pricing = {
            "AWS_S3": {
                "storage_gb": 0.023,
                "egress_gb": 0.09,
                "type": "Object Storage",
            },
            "Azure_Blob": {
                "storage_gb": 0.0184,
                "egress_gb": 0.10,
                "type": "Object Storage",
            },
            "Google_Cloud": {
                "storage_gb": 0.020,
                "egress_gb": 0.08,
                "type": "Object Storage",
            },
            "CVO": {
                "storage_gb": 0.060,
                "egress_gb": 0.09,
                "type": "NetApp Managed File",
            },
            "FSx_for_NetApp_ONTAP": {
                "storage_gb": 0.045,
                "egress_gb": 0.09,
                "type": "NetApp Managed File",
            },
            "Azure_NetApp_Files_Standard": {
                "storage_gb": 0.10,
                "egress_gb": 0.10,
                "type": "NetApp Managed File",
            },
        }

        results = {}
        for provider, rates in pricing.items():
            monthly_storage = effective_tb * 1024 * rates["storage_gb"]
            monthly_egress = (
                effective_tb * 1024 * (hot_percent / 100) * rates["egress_gb"]
            )
            three_year_tco = (monthly_storage + monthly_egress) * 36 * growth_factor

            results[provider] = {
                "type": rates["type"],
                "monthly_storage_usd": round(monthly_storage, 2),
                "monthly_egress_usd": round(monthly_egress, 2),
                "three_year_tco_usd": round(three_year_tco, 2),
            }

        # Smart recommendation logic
        lower_profile = workload_profile.lower()
        needs_file_protocol = any(
            word in lower_profile
            for word in ["nfs", "smb", "file share", "file protocol", "ontap", "cifs"]
        )

        if needs_file_protocol:
            # Prioritize NetApp-managed services
            file_options = {
                k: v for k, v in results.items() if v["type"] == "NetApp Managed File"
            }
            best = min(
                file_options, key=lambda p: file_options[p]["three_year_tco_usd"]
            )
            reason = "Recommended because the workload requires NFS/SMB protocol compatibility (NetApp-managed file services preserve ONTAP features)."
        else:
            # Pure cost winner
            best = min(results, key=lambda p: results[p]["three_year_tco_usd"])
            reason = "Recommended as the lowest 3-year TCO for pure object storage workloads."

        return {
            "effective_capacity_after_dedup_tb": round(effective_tb, 2),
            "costs": results,
            "recommended_provider": best.replace("_", " "),
            "three_year_tco_recommended_usd": results[best]["three_year_tco_usd"],
            "reason": reason,
            "note": "NetApp-managed options preserve NFS/SMB and ONTAP features but cost more than object storage.",
        }
