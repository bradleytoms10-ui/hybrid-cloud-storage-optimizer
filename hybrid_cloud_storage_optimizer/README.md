# Hybrid Cloud Storage Optimizer AI Agent

**Multi-agent AI system that analyzes on-prem NetApp storage and intelligently recommends optimal hybrid-cloud migrations.**

Built to showcase my 5+ years as a Solutions Architect at NetApp and 8 months as an AI Analyst at CACI.

### What It Does
- Analyzes ONTAP configs (capacity, utilization, NFS workloads, dedup, snapshots)
- Calculates **real 2026 TCO** across 6 providers (AWS S3, Azure Blob, Google Cloud, CVO, FSx for NetApp ONTAP, Azure NetApp Files)
- **Smart recommendation logic** — prefers NetApp-managed file services when NFS/SMB compatibility is needed
- Generates a full executive migration plan with phases, tools, risks, timeline, rollback, and Mermaid diagram
- Includes an interactive **Streamlit web UI** for live demos

### Live Demo
You can try the interactive UI locally:
```bash
cd hybrid_cloud_storage_optimizer
.venv/bin/streamlit run src/hybrid_cloud_storage_optimizer/streamlit_app.py