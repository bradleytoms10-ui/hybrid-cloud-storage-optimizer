# Hybrid Cloud Storage Optimizer AI Agent

**Multi-agent AI system that analyzes on-prem NetApp-style storage and intelligently recommends optimal hybrid-cloud migrations.**

### 🔗 [Live Demo](https://hybrid-cloud-storage-optimizer-xjgtfuiuevzub2uugw4h2p.streamlit.app/)

> Hosted on Streamlit Community Cloud. Idle apps sleep — the first load after inactivity takes ~30s to wake.

Built to showcase my 5+ years as a Solutions Architect at NetApp and 8 months as an AI Analyst at CACI.

### What It Does
- Analyzes ONTAP configs (capacity, utilization, NFS workloads, dedup, snapshots)
- Builds a **business case**: computes the % 3-year TCO reduction vs the customer's current on-prem spend and whether it meets their target (e.g., 30%)
- Models **performance cost**: provisioned throughput (MBps) adds cost for throughput-billed services (FSxN, CVO), so quotes aren't capacity-only
- Calculates **2026 total cost of ownership (TCO)** across 6 providers (planning-grade list-price estimates):
  - AWS S3, Azure Blob, Google Cloud (object storage)
  - Cloud Volumes ONTAP (CVO), FSx for NetApp ONTAP, Azure NetApp Files (managed file services)
- **NetApp FabricPool cold-tiering** (toggle, default on) — tiers cold/archival data from the managed performance tier to low-cost object storage, modeling realistic ONTAP economics
- **Solutions-Engineer context awareness** — a Customer Discovery form (cloud footprint, performance posture, budget priority, compliance, existing NetApp ELA, cloud-exit strategy) plus **artifact uploads** (RFPs, assessments, monitoring exports as PDF/CSV/text) feed a dedicated **discovery agent** that produces structured context for a transparent multi-factor scoring engine — returning a *ranked* trade-off shortlist with rationale, not a one-size-fits-all default
- **Smart recommendation logic** — weighs cost, cloud affinity, performance, compliance, licensing, and strategy; prefers NetApp-managed file services when NFS/SMB is required, but adapts the pick to the customer's context
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
   - `agents.yaml` — defines four specialized agents (requirements/discovery, storage analyst, cost estimator, migration architect) with roles, goals, and backstories
   - `tasks.yaml` — defines sequential tasks with clear expected outputs  
   Updated `crew.py` with the official `@CrewBase` pattern. The LLM is set once from the
   `MODEL` environment variable (default `groq/llama-3.3-70b-versatile`) as a single source of truth.

5. **Custom Tool + Smart Logic**  
   Built a real `StorageCostCalculatorTool` over a framework-free TCO engine
   (`tools/pricing.py`) with 2026 pricing for 6 providers (including CVO, FSx for
   NetApp ONTAP, and Azure NetApp Files). TCO is summed month-by-month with
   compounded growth (not a flat multiplier), inputs are validated, and pricing
   assumptions/exclusions are documented. Recommendation logic is protocol-aware
   (prefers NetApp-managed file services when NFS/SMB is required).

6. **Typed Data Contract Between Agents**  
   The storage analyst emits a validated Pydantic `StorageAnalysis` object (`models.py`),
   so the cost estimator receives type-checked fields (effective capacity, protocol need)
   instead of parsing free-form text.

7. **Tests, Error Handling & CI**  
   Deterministic `pytest` suite for the pricing engine (no API calls), friendly
   error messages for bad/missing API keys (instead of raw tracebacks), and a
   GitHub Actions pipeline that runs ruff + black + pytest on every push. The live
   crew smoke test is a separate manual job, so a missing secret never breaks CI.

8. **Interactive UI + Deployment**  
   A Streamlit web UI for live demos, a multi-stage Docker image, env-driven
   observability (structured logging, CrewAI tracing, and optional Langfuse LLM
   tracing), and Streamlit Cloud deployment. See [DEPLOYMENT.md](DEPLOYMENT.md).

The project uses a clean `src/` layout with `pyproject.toml` + `uv` for reproducible installs.

#### Roadmap
Live cloud-pricing API integration, cold-tier (FabricPool/Glacier) modeling, and a
hosted Langfuse tracing dashboard.


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

**Tests & quality** (deterministic, no API key needed)
```bash
make test          # uv run pytest -q
make check         # ruff + black --check (matches CI)
make format        # auto-format + auto-fix before committing
```

**Pre-commit hooks** (auto-run black + ruff on every commit, so CI never fails on formatting)
```bash
uv sync                                                  # installs pre-commit (dev group)
uv run pre-commit install --config ../.pre-commit-config.yaml
```

**Docker**
```bash
docker build -t hcso:latest .
docker run --rm -p 8501:8501 --env-file .env hcso:latest
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for Docker details, hosted Streamlit Cloud
setup, secrets handling, and observability env vars.

