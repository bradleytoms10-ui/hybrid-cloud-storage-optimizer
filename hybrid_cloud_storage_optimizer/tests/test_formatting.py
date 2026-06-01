"""Tests for deterministic output sanitization."""

from hybrid_cloud_storage_optimizer.formatting import clean_output, sanitize_mermaid


def test_fixes_invalid_mermaid_edge():
    bad = "A[Assessment] -->|Evaluate config|> B[Design]"
    fixed = sanitize_mermaid(bad)
    assert "|>" not in fixed
    assert "-->|Evaluate config| B[Design]" in fixed


def test_leaves_valid_mermaid_untouched():
    good = "A[X] -->|label| B[Y]"
    assert sanitize_mermaid(good) == good


def test_handles_multiple_edges():
    bad = "A-->|a|>B\nB-->|b|>C"
    fixed = clean_output(bad)
    assert "|>" not in fixed


def test_empty_safe():
    assert clean_output("") == ""
