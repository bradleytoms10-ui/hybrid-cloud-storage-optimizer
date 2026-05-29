"""Environment validation and human-friendly error framing.

Keeps the noisy provider/LiteLLM tracebacks out of the user's face: we validate
required configuration up front and translate common runtime failures (bad/missing
API key) into a single clear sentence.
"""

from __future__ import annotations

import os

# Map a model provider prefix to the env var that holds its API key.
_PROVIDER_KEYS = {
    "groq/": "GROQ_API_KEY",
    "openai/": "OPENAI_API_KEY",
    "anthropic/": "ANTHROPIC_API_KEY",
    "gemini/": "GEMINI_API_KEY",
    "google/": "GEMINI_API_KEY",
}


class ConfigError(RuntimeError):
    """Raised when required environment configuration is missing."""


def required_key_for(model: str) -> str | None:
    for prefix, key in _PROVIDER_KEYS.items():
        if model.startswith(prefix):
            return key
    return None


def validate_environment(model: str) -> None:
    """Raise ConfigError with actionable guidance if the API key is missing."""
    key_name = required_key_for(model)
    if key_name and not os.getenv(key_name):
        raise ConfigError(
            f"Missing {key_name}. Copy .env.example to .env and set {key_name} "
            f"(for Groq, create one at https://console.groq.com/keys), then re-run."
        )


def friendly_error(exc: Exception) -> str:
    """Translate a runtime exception into a concise, user-facing message."""
    text = str(exc).lower()
    if "invalid_api_key" in text or "invalid api key" in text or "401" in text:
        return (
            "Authentication failed: your API key was rejected. Check GROQ_API_KEY "
            "in .env (no quotes/extra spaces), confirm it is active in the Groq "
            "console, and fully restart the process so the new value is loaded."
        )
    if "rate limit" in text or "429" in text:
        return "Rate limited by the model provider. Wait a moment and try again."
    if "tool_use_failed" in text or "failed to call a function" in text:
        return (
            "The model produced a malformed tool call (a known Groq/Llama quirk). "
            "Re-run; if it persists, try a different MODEL in .env (e.g. a larger "
            "Llama or an OpenAI/Anthropic model with stronger function-calling)."
        )
    if isinstance(exc, ConfigError):
        return str(exc)
    return f"The crew failed to run: {exc}"
