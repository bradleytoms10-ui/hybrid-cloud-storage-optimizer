"""Deterministic clean-up of LLM-generated output.

Some fixes can't be reliably enforced by prompting alone — notably the model's
habit of emitting invalid Mermaid edges like ``A -->|label|> B`` (a stray ``>``
after the closing pipe). We repair these in code so rendered diagrams are always
valid, independent of model behaviour.
"""

from __future__ import annotations

import re

# Matches the invalid "|>" that Llama appends to labeled Mermaid edges.
_BAD_MERMAID_EDGE = re.compile(r"\|>")


def sanitize_mermaid(text: str) -> str:
    """Repair common invalid Mermaid syntax in a block of markdown text."""
    if not text:
        return text
    # `-->|label|> Node`  ->  `-->|label| Node`
    return _BAD_MERMAID_EDGE.sub("|", text)


def clean_output(text: str) -> str:
    """Apply all deterministic output fixes before display/persistence."""
    return sanitize_mermaid(text)
