"""Tests for deterministic artifact text extraction (no LLM, no network)."""

from hybrid_cloud_storage_optimizer.tools import artifacts


def test_extract_plain_text():
    out = artifacts.extract_text("notes.txt", b"hello world")
    assert out == "hello world"


def test_extract_csv_preview():
    data = b"name,tb\nvol1,100\nvol2,200\n"
    out = artifacts.extract_text("export.csv", data)
    assert "name | tb" in out
    assert "vol1 | 100" in out


def test_csv_row_cap():
    rows = "a,b\n" + "\n".join(f"{i},{i}" for i in range(100))
    out = artifacts.extract_text("big.csv", rows.encode())
    assert "more rows" in out


def test_unsupported_extension_is_skipped_gracefully():
    out = artifacts.extract_text("diagram.png", b"\x89PNG...")
    assert "Unsupported file type" in out


def test_per_file_truncation():
    out = artifacts.extract_text("big.txt", b"x" * 20000)
    assert len(out) <= artifacts.MAX_CHARS_PER_FILE + len("\n…[truncated]")
    assert out.endswith("[truncated]")


def test_combine_labels_and_caps():
    files = [("a.txt", b"alpha"), ("b.txt", b"beta")]
    combined = artifacts.combine_artifacts(files)
    assert "Uploaded artifact: a.txt" in combined
    assert "alpha" in combined and "beta" in combined


def test_combine_empty():
    assert artifacts.combine_artifacts([]) == ""
