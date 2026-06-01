# Deployment Guide

Three ways to run the Hybrid Cloud Storage Optimizer: locally, in Docker, or as a
hosted Streamlit demo.

## Secrets

The app needs a `GROQ_API_KEY` (provider key for the LLM). It is **never** committed
— `.env` is gitignored. Set it differently per environment:

| Environment | Where the key goes |
|---|---|
| Local | `.env` file (copy from `.env.example`) |
| Docker | `-e GROQ_API_KEY=...` or `--env-file .env` at `docker run` |
| Streamlit Cloud | App → Settings → **Secrets** |
| GitHub Actions | Repo → Settings → Secrets and variables → Actions → `GROQ_API_KEY` |

If a key is ever exposed, rotate it at https://console.groq.com/keys.

## 1. Local (uv)

```bash
cp .env.example .env        # add your GROQ_API_KEY
uv sync
uv run streamlit run src/hybrid_cloud_storage_optimizer/streamlit_app.py
```

## 2. Docker

```bash
# Build
docker build -t hcso:latest .

# Run the Streamlit UI (default CMD) on http://localhost:8501
docker run --rm -p 8501:8501 --env-file .env hcso:latest

# Or run the CLI crew instead of the UI
docker run --rm --env-file .env hcso:latest crewai run
```

The image is a multi-stage uv build, runs as a non-root user, and bakes in a
reproducible virtualenv from `uv.lock`.

## 3. Streamlit Community Cloud (hosted demo)

1. Push the repo to GitHub (already done).
2. Go to https://share.streamlit.io and **New app**.
3. Configure:
   - **Repository**: `bradleytoms10-ui/hybrid-cloud-storage-optimizer`
   - **Branch**: `main`
   - **Main file path**: `hybrid_cloud_storage_optimizer/src/hybrid_cloud_storage_optimizer/streamlit_app.py`
4. Under **Advanced settings**, set the **Python version to 3.12**. This is
   required — CrewAI 1.11 has no install candidate on Python 3.13, so the default
   builder will fail with "No matching distribution found for crewai".
5. In the same **Advanced settings → Secrets** box, add:
   ```toml
   GROQ_API_KEY = "gsk_your_key_here"
   MODEL = "groq/llama-3.3-70b-versatile"
   ```
6. Deploy. Dependencies install from the repo-root `requirements.txt`; the app
   bootstraps `sys.path` so the package imports without a local install.

Once live, drop the public URL into the README badge at the top.

## Observability

Set these env vars (locally, in Docker, or in Streamlit secrets) to turn on diagnostics:

```bash
LOG_LEVEL=DEBUG               # verbose app logging
CREWAI_TRACING_ENABLED=true   # CrewAI execution traces
```
