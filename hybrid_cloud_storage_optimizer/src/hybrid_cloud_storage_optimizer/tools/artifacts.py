"""Framework-free extraction of text from uploaded customer artifacts.

Turns RFPs, current-state assessments, and monitoring exports (PDF / CSV / text)
into plain text the agents can analyze. No CrewAI dependency, so it is unit-
testable in isolation. Image diagrams are out of scope (the default text model
cannot read them) — see the roadmap.
"""

from __future__ import annotations

import csv
import io
from typing import List, Sequence, Tuple

# Cap per-file and combined text so large uploads can't blow the context window.
MAX_CHARS_PER_FILE = 8000
MAX_TOTAL_CHARS = 24000

_TEXT_EXTS = {"txt", "md", "log", "json", "yaml", "yml"}


def _ext(filename: str) -> str:
    return filename.lower().rsplit(".", 1)[-1] if "." in filename else ""


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…[truncated]"


def _pdf_to_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "[PDF parsing unavailable: install the 'pypdf' package]"
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - never let a bad file crash the run
        return f"[Could not parse PDF: {exc}]"


def _csv_to_text(data: bytes, max_rows: int = 50) -> str:
    """Render the first rows of a CSV as a readable preview."""
    decoded = data.decode("utf-8", errors="replace")
    rows = list(csv.reader(io.StringIO(decoded)))
    preview = rows[:max_rows]
    lines = [" | ".join(cell for cell in row) for row in preview]
    note = "" if len(rows) <= max_rows else f"\n…[{len(rows) - max_rows} more rows]"
    return "\n".join(lines) + note


def extract_text(filename: str, data: bytes) -> str:
    """Extract plain text from one artifact, capped at MAX_CHARS_PER_FILE."""
    ext = _ext(filename)
    if ext == "pdf":
        text = _pdf_to_text(data)
    elif ext == "csv":
        text = _csv_to_text(data)
    elif ext in _TEXT_EXTS:
        text = data.decode("utf-8", errors="replace")
    else:
        return f"[Unsupported file type '.{ext}' for {filename}; skipped]"
    return _truncate(text, MAX_CHARS_PER_FILE)


def combine_artifacts(files: Sequence[Tuple[str, bytes]]) -> str:
    """Extract and label multiple artifacts into one context block (total-capped).

    ``files`` is a sequence of (filename, data) pairs. Returns "" if none.
    """
    if not files:
        return ""
    blocks: List[str] = []
    used = 0
    for filename, data in files:
        text = extract_text(filename, data)
        block = f"--- Uploaded artifact: {filename} ---\n{text}"
        if used + len(block) > MAX_TOTAL_CHARS:
            blocks.append("…[remaining artifacts omitted to fit context budget]")
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)
