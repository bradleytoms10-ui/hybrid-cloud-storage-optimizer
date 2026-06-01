"""Deterministic unit tests for the TCO pricing engine.

These tests exercise pure logic only (no LLM, no network), so they run fast and
free in CI. Run with: ``uv run pytest``.
"""

import math

import pytest

from hybrid_cloud_storage_optimizer.tools import pricing


# --------------------------------------------------------------------------- #
# Effective capacity & protocol detection
# --------------------------------------------------------------------------- #
def test_effective_capacity_applies_dedup():
    assert pricing.effective_capacity_tb(350, 2.0) == 175.0
    assert pricing.effective_capacity_tb(100, 1.0) == 100.0


def test_effective_capacity_rejects_bad_inputs():
    with pytest.raises(ValueError):
        pricing.effective_capacity_tb(0, 2.0)
    with pytest.raises(ValueError):
        pricing.effective_capacity_tb(100, 0.5)  # ratio < 1 is invalid


@pytest.mark.parametrize(
    "profile,expected",
    [
        ("heavy NFS workloads", True),
        ("SMB file shares for finance", True),
        ("legacy CIFS exports", True),
        ("ONTAP cluster migration", True),
        ("cloud-native S3 object archive", False),
        ("", False),
    ],
)
def test_needs_file_protocol(profile, expected):
    assert pricing.needs_file_protocol(profile) is expected


# --------------------------------------------------------------------------- #
# TCO math
# --------------------------------------------------------------------------- #
def test_known_value_storage_only_no_growth():
    # 1 TB, no hot data (no egress), no growth, 1 year on AWS S3.
    # Expected = 1024 GB * $0.023 * 12 months = $282.624 -> 282.62
    costs = pricing.calculate_tco(
        effective_tb=1.0, hot_percent=0, annual_growth_percent=0, horizon_years=1
    )
    assert costs["AWS_S3"]["horizon_tco_usd"] == pytest.approx(282.62, abs=0.01)
    assert costs["AWS_S3"]["initial_monthly_egress_usd"] == 0.0


def test_growth_increases_tco_but_less_than_flat_multiplier():
    """Regression guard against the old bug that multiplied every month by the
    full 3-year growth factor. Compounded growth must lie strictly between the
    no-growth total and that (incorrect) inflated total."""
    no_growth = pricing.calculate_tco(effective_tb=175, annual_growth_percent=0)[
        "AWS_S3"
    ]["horizon_tco_usd"]
    with_growth = pricing.calculate_tco(effective_tb=175, annual_growth_percent=15)[
        "AWS_S3"
    ]["horizon_tco_usd"]
    flat_buggy = no_growth * (1.15**3)  # the old over-counting behaviour

    assert with_growth > no_growth
    assert with_growth < flat_buggy


def test_all_six_providers_present():
    costs = pricing.calculate_tco(effective_tb=100)
    assert set(costs) == set(pricing.provider_table())
    assert len(costs) == 6


def test_calculate_tco_validates_inputs():
    for kwargs in (
        {"effective_tb": 0},
        {"effective_tb": 10, "hot_percent": 150},
        {"effective_tb": 10, "annual_growth_percent": -5},
        {"effective_tb": 10, "horizon_years": 0},
    ):
        with pytest.raises(ValueError):
            pricing.calculate_tco(**kwargs)


# --------------------------------------------------------------------------- #
# Recommendation logic
# --------------------------------------------------------------------------- #
def test_recommends_managed_file_when_protocol_required():
    costs = pricing.calculate_tco(effective_tb=175)
    rec = pricing.recommend(costs, file_protocol_required=True)
    key = rec["recommended_provider_key"]
    assert pricing.PROVIDER_RATES[key].category == pricing.NETAPP_MANAGED_FILE
    # FSxN is the cheapest managed-file option at these rates.
    assert key == "FSx_for_NetApp_ONTAP"


def test_recommends_cheapest_when_no_protocol_requirement():
    costs = pricing.calculate_tco(effective_tb=175)
    rec = pricing.recommend(costs, file_protocol_required=False)
    cheapest = min(costs, key=lambda p: costs[p]["horizon_tco_usd"])
    assert rec["recommended_provider_key"] == cheapest


def test_build_report_end_to_end_nfs():
    report = pricing.build_report(
        raw_or_used_tb=350,
        dedup_ratio=2.0,
        hot_percent=20,
        annual_growth_percent=15,
        workload_profile="heavy NFS workloads, ONTAP",
    )
    assert report["effective_capacity_after_dedup_tb"] == 175.0
    assert report["needs_file_protocol"] is True
    assert report["recommended_provider"] == "FSx for NetApp ONTAP"
    # FabricPool tiering is on by default, so FSxN reflects the blended (tiered) TCO.
    assert report["assumptions"]["fabricpool_tiering_enabled"] is True
    assert math.isclose(
        report["three_year_tco_recommended_usd"], 361733.02, rel_tol=1e-3
    )
    assert report["assumptions"]["pricing_as_of"] == pricing.PRICING_AS_OF


def test_build_report_untiered_matches_list_price_tco():
    report = pricing.build_report(
        raw_or_used_tb=350,
        dedup_ratio=2.0,
        workload_profile="heavy NFS workloads, ONTAP",
        enable_tiering=False,
    )
    assert math.isclose(
        report["three_year_tco_recommended_usd"], 501964.33, rel_tol=1e-3
    )


def test_build_report_surfaces_validation_errors_via_tool(monkeypatch):
    # build_report should raise on bad input (tool layer converts to a message).
    with pytest.raises(ValueError):
        pricing.build_report(raw_or_used_tb=-5)


# --------------------------------------------------------------------------- #
# FabricPool cold-tiering
# --------------------------------------------------------------------------- #
def test_tiering_lowers_managed_file_tco_but_not_object():
    tiered = pricing.calculate_tco(effective_tb=175, enable_tiering=True)
    untiered = pricing.calculate_tco(effective_tb=175, enable_tiering=False)

    # Managed-file targets get cheaper with tiering on.
    for key in ("FSx_for_NetApp_ONTAP", "CVO", "Azure_NetApp_Files_Standard"):
        assert tiered[key]["horizon_tco_usd"] < untiered[key]["horizon_tco_usd"]
        assert tiered[key]["fabricpool_tiering_applied"] is True

    # Object storage is unaffected by tiering.
    for key in ("AWS_S3", "Azure_Blob", "Google_Cloud"):
        assert tiered[key]["horizon_tco_usd"] == untiered[key]["horizon_tco_usd"]
        assert tiered[key]["fabricpool_tiering_applied"] is False


def test_tiering_blended_rate_math():
    # hot 20% on FSxN ($0.045) + cold 80% on S3 capacity tier ($0.023)
    costs = pricing.calculate_tco(effective_tb=100, hot_percent=20, enable_tiering=True)
    expected = 0.20 * 0.045 + 0.80 * pricing.FABRICPOOL_CAPACITY_TIER_RATE
    assert costs["FSx_for_NetApp_ONTAP"][
        "effective_storage_rate_per_gb"
    ] == pytest.approx(expected, abs=1e-6)


def test_tiering_off_reproduces_list_rate():
    costs = pricing.calculate_tco(effective_tb=100, enable_tiering=False)
    fsx = costs["FSx_for_NetApp_ONTAP"]
    assert fsx["effective_storage_rate_per_gb"] == fsx["list_storage_rate_per_gb"]


def test_explicit_file_protocol_flag_overrides_text_inference():
    # Workload text has NO file-protocol keyword, but the explicit flag wins:
    # the report must require a managed-file recommendation.
    report = pricing.build_report(
        raw_or_used_tb=175,
        dedup_ratio=1.0,
        workload_profile="mixed hot/cold data, archival 80%",  # no NFS/SMB token
        file_protocol_required=True,
    )
    assert report["needs_file_protocol"] is True
    assert report["recommended_provider"] == "FSx for NetApp ONTAP"

    # And explicitly False forces object storage even if text mentions NFS.
    report2 = pricing.build_report(
        raw_or_used_tb=175,
        dedup_ratio=1.0,
        workload_profile="heavy NFS workloads",
        file_protocol_required=False,
    )
    assert report2["needs_file_protocol"] is False
    assert (
        pricing.PROVIDER_RATES[
            report2["recommended_provider"].replace(" ", "_")
        ].category
        == pricing.OBJECT_STORAGE
    )
