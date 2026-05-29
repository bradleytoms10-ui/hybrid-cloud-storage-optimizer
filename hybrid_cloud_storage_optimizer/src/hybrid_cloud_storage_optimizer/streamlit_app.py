import os

import streamlit as st

from hybrid_cloud_storage_optimizer.crew import (
    DEFAULT_MODEL,
    HybridCloudStorageOptimizer,
)
from hybrid_cloud_storage_optimizer.env import (
    ConfigError,
    friendly_error,
    validate_environment,
)

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

if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
    inputs = {
        "storage_config": storage_config,
        "workload_profile": workload_profile,
    }
    try:
        validate_environment(os.getenv("MODEL", DEFAULT_MODEL))
        with st.spinner("Agents are collaborating... This may take 20–40 seconds"):
            result = HybridCloudStorageOptimizer().crew().kickoff(inputs=inputs)
        st.success("✅ Analysis Complete!")
        st.markdown(result)
    except ConfigError as exc:
        st.warning(str(exc))
    except Exception as exc:  # noqa: BLE001 - show one clean message, not a traceback
        st.error(friendly_error(exc))

st.caption("Built with CrewAI + Groq • Powered by your NetApp + CACI experience")
