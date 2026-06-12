"""Deterministic tests for workload segmentation normalization."""

from hybrid_cloud_storage_optimizer.tools import segmentation


def test_coerce_workload_type_tokens():
    assert segmentation.coerce_workload_type("block") == "block"
    assert segmentation.coerce_workload_type("Oracle SAN / iSCSI LUNs") == "block"
    assert segmentation.coerce_workload_type("VMware datastores") == "block"
    assert segmentation.coerce_workload_type("NFS/SMB shares") == "file"
    assert segmentation.coerce_workload_type("home directories") == "file"
    assert segmentation.coerce_workload_type("archive") == "object"
    assert segmentation.coerce_workload_type("cold backup retention") == "object"
    assert segmentation.coerce_workload_type("???") is None
    assert segmentation.coerce_workload_type("") is None
    assert segmentation.coerce_workload_type(None) is None


def test_normalize_segments_happy_path():
    segments = segmentation.normalize_segments(
        [
            {"name": "File services", "workload_type": "file", "capacity_tb": 90},
            {
                "name": "Oracle SAN",
                "workload_type": "iscsi",
                "capacity_tb": 45,
                "hot_data_percent": 60,
                "growth_rate_percent": 10,
            },
            {"name": "Archive", "workload_type": "archive", "capacity_tb": 40},
        ],
        default_hot_percent=20,
        default_growth_percent=15,
    )
    assert [s.workload_type for s in segments] == ["file", "block", "object"]
    assert segmentation.total_capacity_tb(segments) == 175.0
    # Per-segment values respected; defaults applied otherwise.
    assert segments[1].hot_percent == 60 and segments[1].growth_rate_percent == 10
    assert segments[0].hot_percent == 20 and segments[0].growth_rate_percent == 15
    # Archive default hot is low, not the blended default.
    assert segments[2].hot_percent == segmentation.ARCHIVE_DEFAULT_HOT_PERCENT


def test_normalize_segments_drops_invalid_entries():
    segments = segmentation.normalize_segments(
        [
            {"name": "ok", "workload_type": "file", "capacity_tb": 10},
            {"name": "no capacity", "workload_type": "file"},
            {"name": "zero", "workload_type": "file", "capacity_tb": 0},
            {"name": "negative", "workload_type": "block", "capacity_tb": -5},
            {"name": "unknown type", "workload_type": "???", "capacity_tb": 10},
            {"name": "bad capacity", "workload_type": "file", "capacity_tb": "lots"},
            "not even a dict",
        ]
    )
    assert len(segments) == 1
    assert segments[0].name == "ok"


def test_normalize_segments_empty_inputs():
    assert segmentation.normalize_segments(None) == []
    assert segmentation.normalize_segments([]) == []


def test_normalize_segments_invalid_hot_growth_fall_back():
    (segment,) = segmentation.normalize_segments(
        [
            {
                "workload_type": "file",
                "capacity_tb": 10,
                "hot_data_percent": 250,  # out of range
                "growth_rate_percent": -3,  # negative
            }
        ],
        default_hot_percent=25,
        default_growth_percent=12,
    )
    assert segment.hot_percent == 25
    assert segment.growth_rate_percent == 12
    assert segment.name == "Segment 1"  # auto-named


def test_accepts_alternate_field_names():
    (segment,) = segmentation.normalize_segments(
        [{"type": "san", "capacity_tb": 20, "hot_percent": 40}]
    )
    assert segment.workload_type == "block"
    assert segment.hot_percent == 40


def test_describe_is_human_readable():
    (segment,) = segmentation.normalize_segments(
        [{"name": "Archive", "workload_type": "object", "capacity_tb": 40}]
    )
    text = segmentation.describe(segment)
    assert "Archive" in text and "40" in text and "object" in text
