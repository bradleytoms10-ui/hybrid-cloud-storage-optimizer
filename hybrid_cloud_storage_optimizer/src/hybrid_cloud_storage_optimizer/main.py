#!/usr/bin/env python
from hybrid_cloud_storage_optimizer.crew import HybridCloudStorageOptimizer


def run():
    """
    Run the Hybrid Cloud Storage Optimizer crew with sample inputs.
    """
    inputs = {
        "storage_config": "ONTAP cluster with 500TB FAS, 70% utilization, heavy NFS workloads, dedup ratio 2:1",
        "workload_profile": "Mixed hot/cold data, frequent access to 20%, archival 80%, expected 15% annual growth",
    }

    result = HybridCloudStorageOptimizer().crew().kickoff(inputs=inputs)

    print("\n" + "=" * 80)
    print("FINAL CREW OUTPUT - HYBRID CLOUD STORAGE OPTIMIZER")
    print("=" * 80)
    print(result)
    print("=" * 80)


if __name__ == "__main__":
    run()
