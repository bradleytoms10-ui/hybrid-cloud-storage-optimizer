# Hybrid Cloud Storage Optimizer AI Agent

**Multi-agent AI system that analyzes on-prem NetApp-style storage and intelligently recommends optimal hybrid-cloud migrations.**

Built to showcase my 5+ years as a Solutions Architect at NetApp and 8 months as an AI Analyst at CACI.

### What It Does
- Analyzes ONTAP configs (capacity, utilization, NFS workloads, dedup, snapshots)
- Calculates **accurate 2026 TCO** across 6 providers:
  - AWS S3, Azure Blob, Google Cloud (object storage)
  - Cloud Volumes ONTAP (CVO), FSx for NetApp ONTAP, Azure NetApp Files (managed file services)
- **Smart recommendation logic** — automatically prefers NetApp-managed file services when NFS/SMB protocol compatibility is needed, otherwise chooses the lowest-cost option
- Generates a full executive-ready migration plan with phases, tools (Terraform, NetApp Cloud Volumes ONTAP, etc.), risks, timeline, rollback strategy, and Mermaid diagram
- Includes an interactive **Streamlit web UI** for live demos

### Project Overview
Hybrid Cloud Storage Optimizer is a multi-agent AI system I built to demonstrate real-world solutions architecture skills. It takes a mock on-prem storage configuration (inspired by my NetApp experience) and automatically:

* Analyzes capacity, performance, inefficiencies, and optimization opportunities
* Estimates realistic migration costs and 3-year TCO using a custom Python calculator tool
* Provides protocol-aware recommendations (object storage vs NetApp-managed file services)
* Generates a professional phased migration plan with risks, tools, timeline, rollback, and Mermaid diagram

**The goal:** Show how I bridge on-premises storage expertise with modern hybrid-cloud AI automation.

### Steps I Took to Build It (Professional CI/CD-Ready Setup)

1. **GitHub-First Repo Setup**  
   Created a clean public repository with README, Python `.gitignore`, and MIT license. Initialized locally with `git init`, connected via `git remote add origin`, and pulled the remote files.

2. **Isolated Python Environment (Best Practice)**  
   On macOS, upgraded from system Python 3.9 to Python 3.12 via Homebrew. Created a dedicated virtual environment inside the project using `uv` (CrewAI’s modern dependency manager).

3. **CrewAI Framework + Groq LLM**  
   Installed CrewAI with `crewai create crew hybrid-cloud-storage-optimizer`. Chose Groq as the provider and added LiteLLM for reliable model support. Upgraded to Llama-3.3-70B-versatile for better reasoning.

4. **YAML-First Configuration **  
   Replaced the default demo with declarative YAML files:
   - `agents.yaml` — defines three specialized agents with roles, goals, and backstories
   - `tasks.yaml` — defines sequential tasks with clear expected outputs  
   Updated `crew.py` with the official `@CrewBase` pattern. The LLM is set once from the
   `MODEL` environment variable (default `groq/llama-3.3-70b-versatile`) as a single source of truth.

5. **Custom Tool + Smart Logic**  
   Built a real `StorageCostCalculatorTool` with 2026 pricing for 6 providers (including CVO, FSx for NetApp ONTAP, and Azure NetApp Files). Added intelligent recommendation logic that considers NFS/SMB protocol needs.

6. **Typed Data Contract Between Agents**  
   The storage analyst emits a validated Pydantic `StorageAnalysis` object (`models.py`),
   so the cost estimator receives type-checked fields (effective capacity, protocol need)
   instead of parsing free-form text.

7. **Interactive UI + CI**  
   Added a Streamlit web UI for live demos and a GitHub Actions pipeline (linting with
   ruff, format checking with black, and a crew smoke test).

The project uses a clean `src/` layout with `pyproject.toml` + `uv` for reproducible installs.

#### Roadmap (not yet implemented)
Unit tests (`pytest`), Dockerfile, structured logging/tracing, and Streamlit Cloud deployment.


### How to Run

**Setup**
```bash
cd hybrid_cloud_storage_optimizer
cp .env.example .env        # then add your GROQ_API_KEY
uv sync
```

**CLI**
```bash
uv run crewai run
```

**Interactive UI**
```bash
uv run streamlit run src/hybrid_cloud_storage_optimizer/streamlit_app.py
```
