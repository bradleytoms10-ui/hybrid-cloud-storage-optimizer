# Hybrid Cloud Storage Optimizer AI Agent

**A multi-agent AI system that analyzes on-prem NetApp-style storage and intelligently recommends optimal hybrid-cloud migrations.**

Built to showcase my 5+ years as a Solutions Architect at NetApp and 8 months as an AI Analyst at CACI.

### What It Does
- Analyzes mock or real ONTAP configs (capacity, utilization, NFS workloads, dedup, snapshots, etc.)
- Calculates **real 2026 TCO** across 6 providers:
  - AWS S3, Azure Blob, Google Cloud (object storage)
  - Cloud Volumes ONTAP (CVO), FSx for NetApp ONTAP, Azure NetApp Files (managed file services)
- **Smart recommendation engine**: Prefers NetApp-managed file services when NFS/SMB protocol compatibility is needed; otherwise selects the cheapest object storage option
- Generates a full executive migration plan with phases, tools (Terraform, NetApp Cloud Volumes ONTAP, etc.), risks, timeline, rollback strategy, and Mermaid diagram
- Includes a **Streamlit web UI** for easy interactive demos

### Architecture & How It Works
The system is a **sequential multi-agent crew** powered by CrewAI + Groq (Llama-3.3-70B):

1. **Storage Analyst** (NetApp-inspired) → Produces structured JSON analysis
2. **Cloud Cost Estimator** → Calls a custom Python TCO calculator tool with real pricing
3. **Migration Architect** → Synthesizes everything into a professional report

Everything runs locally in one command and takes ~20–40 seconds.

### Tech Stack
- **CrewAI** – multi-agent orchestration with declarative YAML config
- **Groq + Llama-3.3-70B** – fast, high-quality inference
- **Custom Python tool** – accurate TCO calculations (including protocol-aware logic)
- **Streamlit** – interactive web UI
- **uv + pyproject.toml** – reproducible environments
- **GitHub Actions** – CI/CD pipeline
- **Docker** – containerized deployment option

### How to Run

**Local CLI**
```bash
cd hybrid_cloud_storage_optimizer
source .venv/bin/activate
.venv/bin/crewai run
