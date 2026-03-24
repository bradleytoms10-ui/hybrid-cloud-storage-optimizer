# Hybrid Cloud Storage Optimizer AI Agent

**A multi-agent AI system that analyzes on-prem NetApp storage and recommends optimal hybrid-cloud migrations.**

Built as a portfolio project to showcase my 5+ years as a Solutions Architect at NetApp and 8 months as an AI Analyst at CACI.

### What It Does
Given a storage config (e.g. "ONTAP cluster with 500TB FAS, 70% utilization, heavy NFS workloads, dedup ratio 2:1") and a workload profile, the crew:
- Analyzes capacity, performance, dedup, and inefficiencies
- Calculates accurate 2026 TCO for 6 providers (AWS S3, Azure Blob, Google Cloud, CVO, FSx for NetApp ONTAP, Azure NetApp Files)
- Intelligently recommends the best option (cost-only vs. NFS/SMB protocol needs)
- Produces a full executive migration plan with phases, tools, risks, timeline, rollback, and Mermaid diagram

### Tech Stack
- **CrewAI** (multi-agent orchestration)
- **Groq** + Llama-3.3-70B (fast, high-quality inference)
- **Custom Python tool** for accurate TCO calculations
- Declarative YAML configuration 
- `uv` + `pyproject.toml` for reproducible environments

### How to Run
```bash
cd hybrid_cloud_storage_optimizer
source .venv/bin/activate
.venv/bin/crewai run