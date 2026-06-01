"""Lightweight observability: structured logging + tracing/usage helpers.

Tracing and verbose logging are opt-in via environment variables so demos stay
quiet by default but a single env flag turns on full diagnostics:

    CREWAI_TRACING_ENABLED=true   # CrewAI's built-in execution traces
    LOG_LEVEL=DEBUG               # this app's logging verbosity
"""

from __future__ import annotations

import logging
import os

_CONFIGURED = False


def get_logger(name: str = "hcso") -> logging.Logger:
    """Return a configured module logger (idempotent)."""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        )
        _CONFIGURED = True
    return logging.getLogger(name)


def tracing_enabled() -> bool:
    """Whether CrewAI execution tracing should be turned on."""
    return os.getenv("CREWAI_TRACING_ENABLED", "false").lower() == "true"


def init_langfuse() -> bool:
    """Enable Langfuse LLM tracing if its keys are present.

    CrewAI calls models through LiteLLM, so registering Langfuse as a LiteLLM
    callback captures every prompt/response, token count, and latency in the
    Langfuse dashboard. No-op (and safe) when keys or the package are missing, so
    this never breaks a normal run. Requires the optional dependency:
        uv sync --group tracing      (installs the 'langfuse' package)
    and these env vars: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST.
    """
    log = get_logger()
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return False
    try:
        import litellm
    except ImportError:
        return False
    try:
        import langfuse  # noqa: F401
    except ImportError:
        log.warning(
            "LANGFUSE keys set but the 'langfuse' package is not installed; "
            "run `uv sync --group tracing`. Skipping Langfuse."
        )
        return False

    for attr in ("success_callback", "failure_callback"):
        callbacks = list(getattr(litellm, attr, None) or [])
        if "langfuse" not in callbacks:
            callbacks.append("langfuse")
            setattr(litellm, attr, callbacks)
    log.info("Langfuse tracing enabled")
    return True


def log_usage(result) -> None:
    """Log token usage and per-task summary from a CrewOutput, if available."""
    log = get_logger()
    usage = getattr(result, "token_usage", None)
    if usage is not None:
        log.info("Token usage: %s", usage)
    tasks = getattr(result, "tasks_output", None)
    if tasks:
        log.info("Completed %d tasks", len(tasks))
