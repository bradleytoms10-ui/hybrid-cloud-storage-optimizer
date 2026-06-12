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


def merge_run_context(data: Dict[str, object]) -> None:
    """Merge keys into the current run context (used by mid-run task callbacks).

    Typed agent outputs that downstream tools need — the analyst's workload
    ``segments`` and the discovery agent's ``milestones`` — are stashed here the
    moment their task completes, so the cost tool reads them directly and the
    LLM keeps passing only simple scalar tool arguments (the tool_use_failed
    fix). A new dict is set rather than mutating in place, keeping ContextVar
    semantics clean across concurrent Streamlit sessions.
    """
    if not data:
        return
    merged = dict(_run_context.get())
    merged.update(data)
    _run_context.set(merged)


def merge_milestones(new_milestones: object) -> None:
    """Union newly discovered milestones with any already provided by the UI."""
    if not isinstance(new_milestones, (list, tuple)):
        return
    existing = _run_context.get().get("milestones")
    combined: list = list(existing) if isinstance(existing, (list, tuple)) else []
    for item in new_milestones:
        text = str(item or "").strip()
        if text and text not in combined:
            combined.append(text)
    if combined:
        merge_run_context({"milestones": combined})
