# syntax=docker/dockerfile:1
# Multi-stage build using uv for fast, reproducible installs.

FROM python:3.12-slim AS builder

# uv: fast Python package/dependency manager.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (cached layer) using only the lockfiles.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy source and install the project itself.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.12-slim AS runtime

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

# Bring in the prepared virtualenv and the application code.
COPY --from=builder --chown=appuser:appuser /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8501

# Default: serve the Streamlit UI. Override CMD to run the CLI crew instead:
#   docker run --rm -e GROQ_API_KEY=... <image> crewai run
CMD ["streamlit", "run", "src/hybrid_cloud_storage_optimizer/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
