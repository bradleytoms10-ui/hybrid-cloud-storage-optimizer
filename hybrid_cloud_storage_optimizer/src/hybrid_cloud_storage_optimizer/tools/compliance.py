"""Framework-free compliance & data-protection guidance.

Turns a list of compliance regimes plus the target cloud into concrete,
SE-grade considerations (residency, encryption/KMS, audit, immutability) and a
standing NetApp data-protection / ransomware / DR recommendation. This gives the
agents grounded material to present as first-class output sections instead of
hand-waving "ensure compliance." Guidance is general and not legal advice.
"""

from __future__ import annotations

from typing import Dict, List

# Per-regime key storage/data considerations (concise, planning-grade).
_REGIME_GUIDANCE: Dict[str, str] = {
    "gdpr": "EU data residency — pin storage to an EU region; document lawful "
    "basis and data-subject rights (RoPA, erasure).",
    "ccpa": "Honor consumer data access/deletion requests; track data inventory "
    "and sale/sharing opt-outs.",
    "hipaa": "Execute a BAA with the cloud provider; encrypt PHI at rest and in "
    "transit; enforce least-privilege access and audit logging.",
    "pci-dss": "Scope and segment cardholder-data environments; encryption + key "
    "management; restrict and log all access to stored account data.",
    "pci": "Scope and segment cardholder-data environments; encryption + key "
    "management; restrict and log all access to stored account data.",
    "sox": "Immutable retention of financial records (WORM); change control and "
    "auditable access trails.",
    "soc2": "Evidence security/availability controls; continuous monitoring and "
    "access reviews for the audit.",
    "iso27001": "Map storage controls to the ISMS (Annex A): access control, "
    "cryptography, operations security, and supplier management.",
    "iso 27001": "Map storage controls to the ISMS (Annex A): access control, "
    "cryptography, operations security, and supplier management.",
}

# Suggested residency region by cloud when EU residency (GDPR) applies.
_EU_REGION = {
    "aws": "an EU region (e.g. eu-west-1 / eu-central-1)",
    "azure": "an EU region (e.g. West Europe / Germany West Central)",
    "gcp": "an EU region (e.g. europe-west1)",
    "multi": "EU regions in each target cloud",
    "": "an EU region in the target cloud",
}


def _normalize(regimes: List[str]) -> List[str]:
    seen, out = set(), []
    for r in regimes or []:
        key = str(r).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def build_compliance_guidance(
    compliance: List[str], cloud_provider: str = ""
) -> Dict[str, object]:
    """Return structured compliance considerations + residency note."""
    regimes = _normalize(compliance)
    considerations: List[Dict[str, str]] = []
    for regime in regimes:
        text = _REGIME_GUIDANCE.get(regime)
        if text:
            considerations.append({"regime": regime.upper(), "guidance": text})

    residency_note = ""
    if "gdpr" in regimes:
        region = _EU_REGION.get(cloud_provider.lower(), _EU_REGION[""])
        residency_note = f"GDPR in scope — provision storage in {region}."

    return {
        "regimes": [r.upper() for r in regimes],
        "considerations": considerations,
        "residency_note": residency_note,
        # Controls that apply across the listed regimes.
        "baseline_controls": [
            "Encryption at rest and in transit (TLS); enable customer-managed keys "
            "(KMS / Key Vault / Cloud KMS) where mandated.",
            "Least-privilege RBAC, MFA, and immutable audit logging of data access.",
        ],
    }


# NetApp data-protection / ransomware / DR story — a core ONTAP differentiator
# and usually a top-three customer concern. Always surfaced.
DATA_PROTECTION = {
    "ransomware": [
        "SnapLock (WORM) for tamper-proof, immutable retention of critical/financial data.",
        "Autonomous Ransomware Protection (ARP) for on-box anomaly detection.",
        "Tamper-resistant, schedule-based snapshots for rapid point-in-time recovery.",
    ],
    "disaster_recovery": [
        "SnapMirror asynchronous replication to a second region for DR.",
        "Define RPO/RTO targets and size replication frequency to meet them.",
        "Periodic DR failover testing against the replicated copy.",
    ],
    "note": (
        "These ONTAP data-protection capabilities (SnapLock, ARP, snapshots, "
        "SnapMirror) carry over to NetApp-managed cloud file services — a key "
        "advantage over plain object storage for regulated and ransomware-exposed "
        "workloads."
    ),
}


def data_protection_guidance() -> Dict[str, object]:
    """Return the standing ransomware/DR data-protection recommendation."""
    return DATA_PROTECTION
