# hybrid-cloud-storage-optimizer
"Hybrid-Cloud-Storage-Optimizer Agent" – A multi-agent system that:  Analyzes on-prem NetApp-style storage configs (mock data or simple API); Recommends migrations to AWS S3 / Azure Blob / Google Cloud Storage; Estimates costs, risks, and performance; Generates a migration plan + Terraform snippet; Includes a simple Streamlit demo UI.


Project Overview
Hybrid Cloud Storage Optimizer is a multi-agent AI system I built to demonstrate real-world solutions architecture skills. It takes a mock on-prem storage configuration (inspired by my 5 years at NetApp) and automatically:

Analyzes capacity, performance, and optimization opportunities
Estimates migration costs to AWS S3, Azure Blob, or Google Cloud Storage (including 3-year TCO)
Generates a phased migration plan with risks, tools, timeline, and Mermaid architecture diagram

The goal: show how I can bridge on-premises storage expertise with modern hybrid-cloud AI automation — exactly the kind of end-to-end thinking employers want for Solutions Engineer/Architect roles.
Steps I Took to Build It (Professional CI/CD-Ready Setup)

GitHub-First Repo Setup
Created a clean public repository with README, Python .gitignore, and MIT license. Initialized locally with git init, connected via git remote add origin, and pulled the remote files using --allow-unrelated-histories.
Isolated Python Environment (Best Practice)
On macOS I upgraded from the system Python 3.9 to Python 3.12 via Homebrew (brew install python@3.12). Created a dedicated virtual environment inside the project folder using uv (CrewAI’s modern dependency manager) so nothing pollutes my global Python.
CrewAI Framework + Groq LLM
Installed CrewAI with crewai create crew hybrid-cloud-storage-optimizer. Chose Groq as the provider (fast & free tier) with the llama-3.1-8b-instant model. Added LiteLLM (uv add litellm) because CrewAI 1.11+ routes non-native providers (like Groq) through LiteLLM for reliable model support.
YAML-First Configuration (Solutions Architect Style)
Replaced the default demo with declarative YAML files:
agents.yaml — defines three specialized agents with roles, goals, backstories, and explicit LLM assignment.
tasks.yaml — defines sequential tasks with clear expected outputs (JSON, Markdown tables, full reports).
Updated crew.py to wire the agents + tasks using Crew(process=Process.sequential).

Testing & Iteration
Ran crewai run repeatedly, starting with the scaffolded “AI LLMs 2026” demo (which confirmed LLM connectivity), then switched to my custom storage scenario. All changes are version-controlled with Git.
Production-Ready Foundations
The project uses pyproject.toml, uv for reproducible installs, and is structured with src/ layout — ready for GitHub Actions CI/CD, Docker, or deployment to Streamlit Cloud.

What the Demo Agent Does Right Now (Deep Technical Walkthrough)
The system is a sequential multi-agent crew powered by Groq + LiteLLM. When you run it, here’s exactly what happens:

Storage Analyst Agent (NetApp-inspired)
Input: {storage_config} (e.g., “ONTAP cluster with 500TB FAS, 70% utilization, heavy NFS workloads, dedup ratio 2:1”)
It analyzes capacity, deduplication/compression savings, snapshot usage, performance bottlenecks, and flags migration triggers.
Output: Structured JSON with summary, inefficiencies, and recommendations.
Cloud Cost Estimator Agent (CACI-inspired)
Takes the analysis + {workload_profile} (hot/cold mix, growth rate, access patterns).
Researches current 2026 pricing for AWS S3, Azure Blob Storage, Google Cloud Storage.
Calculates: one-time transfer costs, monthly storage, egress fees, 3-year TCO, and sensitivity analysis (±20% growth).
Recommends the best target cloud + rationale.
Output: Markdown table + recommendation paragraph.
Migration Architect Agent
Combines both previous outputs.
Produces a full executive-ready report including:
Phased migration plan (Assess → Pilot → Cutover → Optimize)
Tools (Terraform stubs, NetApp Cloud Volumes ONTAP, SnapMirror)
Risks & mitigations
Timeline & rollback strategy
Mermaid flowchart diagram
Output: Complete Markdown report (ready to copy into presentations).


Everything runs locally in one command. The agents collaborate sequentially (no parallel mode yet) using Groq’s fast inference, so a full run takes ~20–40 seconds.
How to Run It Yourself
Bashcd hybrid_cloud_storage_optimizer
source .venv/bin/activate
.venv/bin/crewai run --inputs '{
  "storage_config": "ONTAP cluster with 500TB FAS, 70% utilization, heavy NFS workloads, dedup ratio 2:1",
  "workload_profile": "Mixed hot/cold data, frequent access to 20%, archival 80%, expected 15% annual growth"
}'