"""Tests that the multi-factor scoring de-biases recommendations.

The point of these is to prove the engine no longer defaults to FSxN regardless
of context — recommendations must shift appropriately with the customer's cloud,
performance, licensing, and strategy.
"""

from hybrid_cloud_storage_optimizer.tools import pricing, scoring
from hybrid_cloud_storage_optimizer.tools.scoring import CustomerContext

# Tiered cost table for a representative 175 TB effective workload.
COSTS = pricing.calculate_tco(effective_tb=175)


def _top_key(context, needs_file_protocol=True):
    ranked = scoring.score_options(
        COSTS, needs_file_protocol=needs_file_protocol, context=context
    )
    return ranked[0]["provider_key"]


def _rank_of(key, context, needs_file_protocol=True):
    ranked = scoring.score_options(
        COSTS, needs_file_protocol=needs_file_protocol, context=context
    )
    return [r["provider_key"] for r in ranked].index(key)


def test_neutral_protocol_defaults_to_fsxn():
    # Preserves prior default behaviour when no context is supplied.
    assert _top_key(CustomerContext()) == "FSx_for_NetApp_ONTAP"


def test_aws_footprint_prefers_fsxn():
    assert _top_key(CustomerContext(cloud_provider="aws")) == "FSx_for_NetApp_ONTAP"


def test_azure_footprint_does_not_default_to_fsxn():
    # The whole point: Azure-heavy customers should NOT get FSxN as #1.
    top = _top_key(CustomerContext(cloud_provider="azure"))
    assert top != "FSx_for_NetApp_ONTAP"
    assert scoring.PROVIDER_PROFILES[top].cloud in ("azure", "any")


def test_azure_performance_ranks_anf_above_fsxn():
    ctx = CustomerContext(
        cloud_provider="azure",
        performance_tier="high",
        budget_sensitivity="performance",
    )
    assert _rank_of("Azure_NetApp_Files_Standard", ctx) < _rank_of(
        "FSx_for_NetApp_ONTAP", ctx
    )


def test_existing_ela_boosts_cvo_above_fsxn():
    ctx = CustomerContext(existing_netapp_ela=True)
    assert _rank_of("CVO", ctx) < _rank_of("FSx_for_NetApp_ONTAP", ctx)


def test_cloud_exit_optionality_favors_portable_cvo():
    ctx = CustomerContext(cloud_provider="multi", cloud_exit_optionality=True)
    assert _top_key(ctx) == "CVO"


def test_archive_without_protocol_prefers_object():
    ctx = CustomerContext(performance_tier="archive")
    top = _top_key(ctx, needs_file_protocol=False)
    assert scoring.PROVIDER_PROFILES[top].netapp_managed is False


def test_protocol_requirement_penalizes_object_below_managed():
    ranked = scoring.score_options(
        COSTS, needs_file_protocol=True, context=CustomerContext()
    )
    top = ranked[0]
    assert scoring.PROVIDER_PROFILES[top["provider_key"]].serves_file_protocol


def test_context_from_dict_tolerates_bad_values():
    ctx = scoring.context_from_dict(
        {
            "cloud_provider": "AWS",
            "performance_tier": "bogus",
            "compliance": "fedramp, hipaa",
        }
    )
    assert ctx.cloud_provider == "aws"
    assert ctx.performance_tier == "standard"  # invalid coerced to default
    assert ctx.compliance == ("fedramp", "hipaa")


def test_context_changes_build_report_recommendation():
    aws = pricing.build_report(
        raw_or_used_tb=350,
        dedup_ratio=2.0,
        workload_profile="heavy NFS",
        context=scoring.context_from_dict({"cloud_provider": "aws"}),
    )
    multi = pricing.build_report(
        raw_or_used_tb=350,
        dedup_ratio=2.0,
        workload_profile="heavy NFS",
        context=scoring.context_from_dict(
            {"cloud_provider": "multi", "cloud_exit_optionality": True}
        ),
    )
    assert aws["recommended_provider"] == "FSx for NetApp ONTAP"
    assert multi["recommended_provider"] == "CVO"
    assert "ranked_options" in aws and len(aws["ranked_options"]) == 6


def test_protocol_required_never_recommends_object_even_when_cheaper():
    # Even with a throughput surcharge making managed file pricier and a cloud
    # mismatch, object storage must not be the #1 pick when NFS is required.
    costs = pricing.calculate_tco(effective_tb=175, provisioned_throughput_mbps=800)
    ranked = scoring.score_options(
        costs,
        needs_file_protocol=True,
        context=CustomerContext(cloud_provider="azure"),
    )
    top = ranked[0]
    assert scoring.PROVIDER_PROFILES[top["provider_key"]].serves_file_protocol
    assert top["eligible"] is True


def test_every_option_has_rationale():
    ranked = scoring.score_options(
        COSTS, needs_file_protocol=True, context=CustomerContext(cloud_provider="aws")
    )
    assert all(isinstance(o["rationale"], list) for o in ranked)
    assert all(0 <= o["total_score"] <= 100 for o in ranked)
