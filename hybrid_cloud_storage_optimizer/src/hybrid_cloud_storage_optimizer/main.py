#!/usr/bin/env python
import os
import sys

from hybrid_cloud_storage_optimizer.crew import (
    DEFAULT_MODEL,
    HybridCloudStorageOptimizer,
)
from hybrid_cloud_storage_optimizer.env import (
    ConfigError,
    friendly_error,
    validate_environment,
)

SAMPLE_INPUTS = {
    "storage_config": (
        "ONTAP cluster with 500TB FAS, 70% utilization, heavy NFS workloads, "
        "dedup ratio 2:1"
    ),
    "workload_profile": (
        "Mixed hot/cold data, frequent access to 20%, archival 80%, "
        "expected 15% annual growth"
    ),
    "enable_tiering": True,
}


def run():
    """Run the Hybrid Cloud Storage Optimizer crew with sample inputs."""
    model = os.getenv("MODEL", DEFAULT_MODEL)
    try:
        validate_environment(model)
        result = HybridCloudStorageOptimizer().crew().kickoff(inputs=SAMPLE_INPUTS)
    except ConfigError as exc:
        print(f"\n[config] {exc}\n", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - surface one clean line, not a wall
        print(f"\n[error] {friendly_error(exc)}\n", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 80)
    print("FINAL CREW OUTPUT - HYBRID CLOUD STORAGE OPTIMIZER")
    print("=" * 80)
    print(result)
    print("=" * 80)


if __name__ == "__main__":
    run()
