import json
import os
import sys
from pathlib import Path

# Make the package importable when run directly (e.g. Streamlit Community Cloud,
# which does not pip-install the local project). src/ is two levels up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from hybrid_cloud_storage_optimizer.crew import (  # noqa: E402
    DEFAULT_MODEL,
    HybridCloudStorageOptimizer,
)
from hybrid_cloud_storage_optimizer.env import (  # noqa: E402
    ConfigError,
    friendly_error,
    validate_environment,
)
from hybrid_cloud_storage_optimizer.formatting import clean_output  # noqa: E402
from hybrid_cloud_storage_optimizer.tools import artifacts  # noqa: E402

st.set_page_config(
    page_title="Hybrid Cloud Storage Optimizer", page_icon="☁️", layout="wide"
)
st.title("☁️ Hybrid Cloud Storage Optimizer")
st.markdown("**AI-powered migration advisor for NetApp ONTAP → Cloud**")

col1, col2 = st.columns(2)

with col1:
    storage_config = st.text_area(
        "Storage Configuration",
        value="ONTAP cluster with 500TB FAS, 70% utilization, heavy NFS workloads, dedup ratio 2:1",
        height=120,
    )

with col2:
    workload_profile = st.text_area(
        "Workload Profile",
        value="Mixed hot/cold data, frequent access to 20%, archival 80%, expected 15% annual growth",
        height=120,
    )

enable_tiering = st.checkbox(
    "Apply NetApp FabricPool cold-tiering to managed-file options",
    value=True,
    help="Tiers cold data from the managed performance tier to low-cost object "
    "storage, substantially lowering NetApp-managed-file TCO.",
)

with st.expander("🧭 Customer Discovery (optional — shapes the recommendation)"):
    st.caption(
        "Provide an SE-style picture of the customer. The more context you give, "
        "the more the recommendation moves beyond a generic default."
    )
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        cloud_provider = st.selectbox(
            "Primary cloud footprint",
            ["(unspecified)", "aws", "azure", "gcp", "multi"],
            help="Existing/target cloud. Steers toward native services.",
        )
        performance_tier = st.selectbox(
            "Performance posture", ["standard", "high", "archive"]
        )
    with dc2:
        budget_sensitivity = st.selectbox(
            "Priority", ["balanced", "cost", "performance"]
        )
        compliance_raw = st.text_input(
            "Compliance regimes (comma-separated)",
            placeholder="e.g. fedramp, hipaa",
        )
    with dc3:
        existing_netapp_ela = st.checkbox("Existing NetApp ELA / BYOL")
        cloud_exit_optionality = st.checkbox("Cloud-exit optionality matters")
    fc1, fc2 = st.columns(2)
    with fc1:
        provisioned_throughput_mbps = st.number_input(
            "Sustained throughput to provision (MBps, 0 = n/a)",
            min_value=0,
            value=0,
            step=100,
            help="Adds performance cost for throughput-billed services (FSxN, CVO).",
        )
    with fc2:
        on_prem_annual_usd = st.number_input(
            "Current on-prem annual storage spend (USD, 0 = unknown)",
            min_value=0,
            value=0,
            step=10000,
            help="Enables the % TCO-reduction business case vs the customer's "
            "current spend.",
        )
    extra_context = st.text_area(
        "Additional context (pain points, constraints, success criteria)",
        height=80,
        placeholder="Free-form notes the agents should weigh.",
    )
    uploaded = st.file_uploader(
        "Upload artifacts (RFPs, assessments, monitoring exports) — PDF/CSV/TXT/MD",
        type=["pdf", "csv", "txt", "md", "log", "json"],
        accept_multiple_files=True,
        help="Text is extracted and given to the agents. Diagrams/images are not "
        "read by the current model. Do not upload confidential data to the public "
        "demo — nothing is persisted, but it is sent to the model provider.",
    )

if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
    context = {
        "cloud_provider": "" if cloud_provider == "(unspecified)" else cloud_provider,
        "performance_tier": performance_tier,
        "budget_sensitivity": budget_sensitivity,
        "existing_netapp_ela": existing_netapp_ela,
        "cloud_exit_optionality": cloud_exit_optionality,
        "compliance": [c.strip() for c in compliance_raw.split(",") if c.strip()],
        "provisioned_throughput_mbps": provisioned_throughput_mbps,
        "on_prem_annual_usd": on_prem_annual_usd,
    }
    profile = workload_profile
    if extra_context.strip():
        profile = f"{workload_profile}\n\nAdditional context: {extra_context.strip()}"
    if uploaded:
        files = [(f.name, f.getvalue()) for f in uploaded]
        artifact_text = artifacts.combine_artifacts(files)
        if artifact_text:
            profile = f"{profile}\n\n{artifact_text}"
    inputs = {
        "storage_config": storage_config,
        "workload_profile": profile,
        "enable_tiering": enable_tiering,
        "customer_context_json": json.dumps(context),
    }
    try:
        validate_environment(os.getenv("MODEL", DEFAULT_MODEL))
        with st.spinner("Agents are collaborating... This may take 20–40 seconds"):
            result = HybridCloudStorageOptimizer().crew().kickoff(inputs=inputs)
        st.success("✅ Analysis Complete!")
        st.markdown(clean_output(str(result)))
    except ConfigError as exc:
        st.warning(str(exc))
    except Exception as exc:  # noqa: BLE001 - show one clean message, not a traceback
        st.error(friendly_error(exc))

st.caption("Built with CrewAI + Groq • Powered by your NetApp + CACI experience")
