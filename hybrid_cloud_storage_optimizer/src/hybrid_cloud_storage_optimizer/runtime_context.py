"""Per-run customer context, passed to the cost tool without the LLM.

Making the LLM serialize a nested JSON string into a tool argument is fragile on
Groq/Llama (escaping errors -> tool_use_failed). Instead we stash the parsed
customer context at crew kickoff and have the calculator read it directly, so the
model only passes simple scalar arguments. A ContextVar keeps this thread-safe
across concurrent Streamlit sessions.
"""

from __future__ import annotations

import contextvars
import json
from typing import Dict

_run_context: contextvars.ContextVar[Dict[str, object]] = contextvars.ContextVar(
    "hcso_run_context", default={}
)


def set_run_context_from_json(context_json: str) -> None:
    """Parse the customer_context_json input and store it for this run."""
    data: Dict[str, object] = {}
    if context_json:
        try:
            parsed = json.loads(context_json)
            if isinstance(parsed, dict):
                data = parsed
        except (ValueError, TypeError):
            data = {}
    _run_context.set(data)


def get_run_context() -> Dict[str, object]:
    """Return the current run's customer context (empty dict if unset)."""
    return _run_context.get()
