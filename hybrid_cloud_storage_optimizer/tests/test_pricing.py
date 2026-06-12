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


def test_throughput_surcharge_applies_only_to_decoupled_providers():
    base = pricing.calculate_tco(effective_tb=175)
    perf = pricing.calculate_tco(effective_tb=175, provisioned_throughput_mbps=500)
    # FSxN and CVO bill throughput separately -> cost rises.
    assert (
        perf["FSx_for_NetApp_ONTAP"]["horizon_tco_usd"]
        > base["FSx_for_NetApp_ONTAP"]["horizon_tco_usd"]
    )
    assert perf["CVO"]["horizon_tco_usd"] > base["CVO"]["horizon_tco_usd"]
    # Object storage and ANF (bundled throughput) are unchanged.
    for key in ("AWS_S3", "Azure_Blob", "Google_Cloud", "Azure_NetApp_Files_Standard"):
        assert perf[key]["horizon_tco_usd"] == base[key]["horizon_tco_usd"]


def test_throughput_cost_math():
    base = pricing.calculate_tco(effective_tb=175)["FSx_for_NetApp_ONTAP"][
        "horizon_tco_usd"
    ]
    perf = pricing.calculate_tco(effective_tb=175, provisioned_throughput_mbps=500)[
        "FSx_for_NetApp_ONTAP"
    ]["horizon_tco_usd"]
    # 500 MBps * $0.78/MBps-mo * 36 months
    assert perf - base == pytest.approx(500 * 0.78 * 36, abs=0.01)


def test_business_case_without_baseline():
    bc = pricing.build_report(
        raw_or_used_tb=350, dedup_ratio=2.0, workload_profile="heavy NFS"
    )["business_case"]
    assert bc["baseline_provided"] is False
    assert "recommended_annual_usd" in bc


def test_business_case_meets_target():
    bc = pricing.build_report(
        raw_or_used_tb=350,
        dedup_ratio=2.0,
        workload_profile="heavy NFS",
        on_prem_annual_usd=220000,
    )["business_case"]
    assert bc["baseline_provided"] is True
    # 3-yr recommended ~361,733 vs 660,000 baseline -> ~45% reduction.
    assert bc["meets_target"] is True
    assert bc["tco_reduction_percent"] > 30


def test_business_case_falls_short():
    bc = pricing.build_report(
        raw_or_used_tb=350,
        dedup_ratio=2.0,
        workload_profile="heavy NFS",
        on_prem_annual_usd=130000,
    )["business_case"]
    assert bc["meets_target"] is False


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


# --------------------------------------------------------------------------- #
# Timeline in the blended report
# --------------------------------------------------------------------------- #
def test_build_report_includes_migration_timeline():
    report = pricing.build_report(raw_or_used_tb=350)
    assert report["migration_timeline"]["source"] == "standard_template"

    aligned = pricing.build_report(
        raw_or_used_tb=350, milestones=["Pilot — Q4 2026", "Cutover — by March 2027"]
    )
    assert aligned["migration_timeline"]["source"] == "customer_milestones"
    assert len(aligned["migration_timeline"]["phases"]) == 6


# --------------------------------------------------------------------------- #
# Segmented reports (per-workload placement)
# --------------------------------------------------------------------------- #
SEGMENTS = [
    {"name": "File services", "workload_type": "file", "capacity_tb": 90},
    {
        "name": "Oracle SAN",
        "workload_type": "block",
        "capacity_tb": 45,
        "hot_data_percent": 60,
    },
    {"name": "Archive", "workload_type": "object", "capacity_tb": 40},
]


def test_segmented_report_places_each_segment_on_its_merits():
    report = pricing.build_segmented_report(
        SEGMENTS, context=pricing.CustomerContext(cloud_provider="aws")
    )
    assert report["segmented"] is True
    by_name = {s["name"]: s for s in report["segments"]}

    # Block segment: object storage and ANF must be ineligible.
    block_excluded = {e["provider"] for e in by_name["Oracle SAN"]["excluded_options"]}
    assert "AWS S3" in block_excluded
    assert "Azure NetApp Files Standard" in block_excluded
    assert by_name["Oracle SAN"]["recommended_provider"] in (
        "FSx for NetApp ONTAP",
        "CVO",
    )

    # File segment: object storage ineligible, managed file recommended.
    file_excluded = {
        e["provider"] for e in by_name["File services"]["excluded_options"]
    }
    assert "AWS S3" in file_excluded
    assert by_name["File services"]["recommended_provider"] == "FSx for NetApp ONTAP"

    # Archive segment: scored with an archive posture -> object storage wins.
    assert by_name["Archive"]["recommended_provider"] == "AWS S3"

    # Capacity and totals roll up exactly.
    assert report["effective_capacity_after_dedup_tb"] == 175.0
    expected_total = round(sum(s["three_year_tco_usd"] for s in report["segments"]), 2)
    assert report["three_year_tco_recommended_usd"] == expected_total
    assert report["needs_file_protocol"] is True
    assert report["needs_block_protocol"] is True


def test_segmented_report_single_provider_alternative():
    report = pricing.build_segmented_report(
        SEGMENTS, context=pricing.CustomerContext(cloud_provider="aws")
    )
    single = report["combined"]["single_provider_alternative"]
    assert single is not None
    # Only a SAN-capable, AWS-deployable service can serve every segment.
    assert single["provider_key"] in ("FSx_for_NetApp_ONTAP", "CVO")
    assert single["three_year_tco_usd"] == pytest.approx(
        report["combined"]["mixed_three_year_tco_usd"] + single["delta_vs_mixed_usd"],
        abs=0.02,
    )


def test_segmented_report_throughput_apportioned_to_non_archive_segments():
    base = pricing.build_segmented_report(SEGMENTS)
    with_throughput = pricing.build_segmented_report(
        SEGMENTS, provisioned_throughput_mbps=900
    )
    by_name_base = {s["name"]: s for s in base["segments"]}
    by_name_tp = {s["name"]: s for s in with_throughput["segments"]}

    def fsx_tco(report_by_name, name):
        options = {
            o["provider_key"]: o for o in report_by_name[name]["ranked_options"]
        }
        return options["FSx_for_NetApp_ONTAP"]["horizon_tco_usd"]

    # Throughput-billed targets get pricier for file/block segments...
    assert fsx_tco(by_name_tp, "File services") > fsx_tco(by_name_base, "File services")
    assert fsx_tco(by_name_tp, "Oracle SAN") > fsx_tco(by_name_base, "Oracle SAN")
    # ...but the archive segment consumes no provisioned throughput.
    assert fsx_tco(by_name_tp, "Archive") == fsx_tco(by_name_base, "Archive")


def test_segmented_report_business_case_uses_mixed_total():
    report = pricing.build_segmented_report(SEGMENTS, on_prem_annual_usd=220_000)
    bc = report["business_case"]
    assert bc["baseline_provided"] is True
    mixed = report["combined"]["mixed_three_year_tco_usd"]
    expected_pct = (220_000 * 3 - mixed) / (220_000 * 3) * 100
    assert bc["tco_reduction_percent"] == pytest.approx(expected_pct, abs=0.1)


def test_segmented_report_falls_back_to_none_without_valid_segments():
    assert pricing.build_segmented_report([]) is None
    assert (
        pricing.build_segmented_report([{"workload_type": "???", "capacity_tb": -1}])
        is None
    )


def test_segmented_report_includes_timeline_and_assumptions():
    report = pricing.build_segmented_report(SEGMENTS, milestones=["Pilot — Q4 2026"])
    assert report["migration_timeline"]["source"] == "customer_milestones"
    assert report["assumptions"]["segment_capacities_are_effective_tb"] is True
    assert len(report["assumptions"]["segments"]) == 3
