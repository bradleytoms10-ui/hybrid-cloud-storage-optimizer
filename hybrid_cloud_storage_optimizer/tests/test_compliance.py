"""Tests for the compliance & data-protection guidance module."""

from hybrid_cloud_storage_optimizer.tools import compliance, pricing, scoring


def test_gdpr_drives_residency_note_per_cloud():
    g = compliance.build_compliance_guidance(["GDPR"], "azure")
    assert "GDPR" in g["residency_note"]
    assert "Europe" in g["residency_note"] or "EU" in g["residency_note"]


def test_regimes_map_to_considerations():
    g = compliance.build_compliance_guidance(["hipaa", "pci-dss"], "aws")
    regimes = {c["regime"] for c in g["considerations"]}
    assert "HIPAA" in regimes and "PCI-DSS" in regimes
    hipaa = next(c for c in g["considerations"] if c["regime"] == "HIPAA")
    assert "BAA" in hipaa["guidance"]


def test_dedupes_and_ignores_unknown():
    g = compliance.build_compliance_guidance(["ISO27001", "iso27001", "bogus"], "")
    regimes = [c["regime"] for c in g["considerations"]]
    assert regimes.count("ISO27001") == 1
    assert all(r != "BOGUS" for r in regimes)


def test_baseline_controls_always_present():
    g = compliance.build_compliance_guidance([], "aws")
    assert any("Encryption" in c for c in g["baseline_controls"])


def test_data_protection_has_ransomware_and_dr():
    dp = compliance.data_protection_guidance()
    assert any("SnapLock" in x for x in dp["ransomware"])
    assert any("SnapMirror" in x for x in dp["disaster_recovery"])


def test_build_report_surfaces_compliance_and_data_protection():
    report = pricing.build_report(
        raw_or_used_tb=350,
        dedup_ratio=2.0,
        workload_profile="heavy NFS, ONTAP",
        context=scoring.context_from_dict(
            {"cloud_provider": "azure", "compliance": ["gdpr", "hipaa"]}
        ),
    )
    assert report["compliance_guidance"]["residency_note"]
    assert "GDPR" in report["compliance_guidance"]["regimes"]
    assert "data_protection" in report
