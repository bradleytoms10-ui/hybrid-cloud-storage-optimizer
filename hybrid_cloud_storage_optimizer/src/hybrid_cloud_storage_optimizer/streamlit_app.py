import json
import os
import re
import sys
from pathlib import Path

# Make the package importable when run directly (e.g. Streamlit Community Cloud,
# which does not pip-install the local project). src/ is two levels up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from hybrid_cloud_storage_optimizer.crew import (  # noqa: E402
    DEFAULT_MODEL,
    HybridCloudStorageOptimizer,
)
from hybrid_cloud_storage_optimizer.env import (  # noqa: E402
    ConfigError,
    friendly_error,
    validate_environment,
)
from hybrid_cloud_storage_optimizer.formatting import clean_output  # noqa: E402
from hybrid_cloud_storage_optimizer.tools import (  # noqa: E402
    artifacts,
    pricing,
    scoring,
)

ACCENT = "#1d4ed8"
MUTED_BAR = "#cbd5e1"

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hybrid Cloud Storage Optimizer",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS — light professional / enterprise ───────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, .stTextArea, .stSelectbox, .stTextInput {
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
}
.block-container { padding-top: 1.4rem; max-width: 1180px; }

/* ── Header ── */
.app-header {
    display: flex; justify-content: space-between; align-items: flex-start;
    padding: 0.4rem 0 1.2rem; border-bottom: 1px solid #e2e8f0; margin-bottom: 1.4rem;
}
.app-header .brand { display: flex; gap: 0.85rem; align-items: flex-start; }
.logo-mark {
    width: 38px; height: 38px; border-radius: 9px; background: #1d4ed8;
    color: #fff; font-weight: 700; font-size: 0.82rem; letter-spacing: 0.02em;
    display: flex; align-items: center; justify-content: center; margin-top: 3px;
}
.app-header h1 {
    font-size: 1.45rem; font-weight: 700; color: #0f172a;
    letter-spacing: -0.015em; margin: 0; padding: 0;
}
.app-header .tagline { font-size: 0.88rem; color: #64748b; margin-top: 3px; }
.app-header .meta {
    text-align: right; font-size: 0.72rem; color: #64748b; line-height: 1.7;
    padding-top: 5px; white-space: nowrap;
}
.app-header .meta b { color: #475569; font-weight: 600; }
.chips { margin-top: 0.7rem; }
.chip {
    display: inline-block; border: 1px solid #e2e8f0; background: #f8fafc;
    color: #475569; border-radius: 6px; padding: 2px 10px;
    font-size: 0.71rem; font-weight: 600; letter-spacing: 0.01em;
    margin-right: 6px; margin-top: 6px;
}

/* ── Section labels ── */
.section-label {
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.09em; color: #475569; margin: 0.9rem 0 0.6rem;
}

/* ── Panels & metric cards ── */
.panel {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 1.1rem 1.3rem; margin-bottom: 1rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.metric-row { display: flex; gap: 0.9rem; margin: 0.4rem 0 1.3rem; flex-wrap: wrap; }
.metric-card {
    flex: 1; min-width: 185px; background: #ffffff;
    border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem 1.15rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.metric-card .mc-label {
    font-size: 0.67rem; color: #64748b; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.07em;
}
.metric-card .mc-value {
    font-size: 1.55rem; font-weight: 700; color: #0f172a; line-height: 1.2;
    margin-top: 5px; letter-spacing: -0.01em; font-variant-numeric: tabular-nums;
}
.metric-card .mc-value.small { font-size: 1.06rem; line-height: 1.35; }
.metric-card .mc-sub { font-size: 0.73rem; color: #94a3b8; margin-top: 4px; }
.metric-card .mc-sub .ok { color: #15803d; font-weight: 600; }
.metric-card .mc-sub .warn { color: #b45309; font-weight: 600; }

/* ── Tables (segments / timeline) ── */
table.ent-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin: 0.2rem 0 0.8rem; }
table.ent-table th {
    text-align: left; font-size: 0.67rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #64748b; font-weight: 700;
    border-bottom: 1px solid #e2e8f0; padding: 7px 10px;
}
table.ent-table td {
    padding: 9px 10px; border-bottom: 1px solid #f1f5f9; color: #0f172a;
    font-variant-numeric: tabular-nums; vertical-align: top;
}
table.ent-table td.num { text-align: right; }
table.ent-table th.num { text-align: right; }
.type-badge {
    display: inline-block; font-size: 0.66rem; font-weight: 700;
    padding: 2px 8px; border-radius: 5px; letter-spacing: 0.05em;
    text-transform: uppercase;
}
.type-file   { background: #eff6ff; color: #1d4ed8; }
.type-block  { background: #f5f3ff; color: #6d28d9; }
.type-object { background: #f0fdfa; color: #0f766e; }
.anchor-note { font-size: 0.74rem; color: #64748b; }

/* ── Agent progress ── */
.agent-step { display: flex; align-items: center; gap: 0.6rem; padding: 0.42rem 0; }
.agent-dot  { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.agent-dot.done    { background: #16a34a; }
.agent-dot.running { background: #1d4ed8; animation: pulse 1.3s infinite; }
.agent-dot.pending { background: #cbd5e1; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
.agent-name { font-size: 0.87rem; color: #334155; }
.agent-name.done    { color: #15803d; }
.agent-name.running { color: #1d4ed8; font-weight: 600; }
.agent-name.pending { color: #94a3b8; }

/* ── Buttons ── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: #1d4ed8; border: none; border-radius: 8px;
    font-weight: 600; font-size: 0.95rem; padding: 0.65rem 1rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.1);
}
div[data-testid="stButton"] > button[kind="primary"]:hover { background: #1e40af; }
div[data-testid="stDownloadButton"] button {
    background: #ffffff; border: 1px solid #e2e8f0; color: #334155;
    border-radius: 8px; font-weight: 600; font-size: 0.84rem;
}

/* ── Tabs ── */
div[data-testid="stTabs"] button { font-weight: 600; font-size: 0.89rem; color: #64748b; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: #1d4ed8; }
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: #1d4ed8; }

/* ── Footer ── */
.app-footer {
    font-size: 0.73rem; color: #94a3b8; margin-top: 2.4rem;
    padding-top: 1rem; border-top: 1px solid #e2e8f0; line-height: 1.7;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
<div class="app-header">
  <div class="brand">
    <div class="logo-mark">HC</div>
    <div>
      <h1>Hybrid Cloud Storage Optimizer</h1>
      <div class="tagline">Migration analysis for NetApp ONTAP estates —
      deterministic {pricing.PRICING_AS_OF[:4]} TCO across six cloud storage targets</div>
      <div class="chips">
        <span class="chip">Multi-agent analysis</span>
        <span class="chip">Deterministic TCO engine</span>
        <span class="chip">Workload segmentation</span>
        <span class="chip">Milestone-aligned planning</span>
        <span class="chip">Compliance-aware</span>
        <span class="chip">FabricPool tiering</span>
      </div>
    </div>
  </div>
  <div class="meta">
    <b>Pricing data</b> {pricing.PRICING_AS_OF} list prices · {pricing.PRICING_REGION}<br>
    <b>Method</b> effective-capacity sizing · monthly compounding<br>
    <b>Output</b> planning-grade estimates, not quotes
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Input form ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Environment</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    storage_config = st.text_area(
        "Storage configuration",
        value=(
            "ONTAP cluster with 500TB FAS, 70% utilization, "
            "heavy NFS workloads, dedup ratio 2:1"
        ),
        height=110,
        help=(
            "Describe the on-prem estate. Distinct workload classes (e.g. an "
            "Oracle SAN slice on iSCSI LUNs, NFS/SMB file services, archive "
            "shares) are detected and priced as separate segments."
        ),
    )
with col2:
    workload_profile = st.text_area(
        "Workload profile",
        value=(
            "Mixed hot/cold data, frequent access to 20%, "
            "archival 80%, expected 15% annual growth"
        ),
        height=110,
        help="Access patterns, growth expectations, performance requirements.",
    )

enable_tiering = st.checkbox(
    "Apply NetApp FabricPool cold-tiering to managed-file options",
    value=True,
    help=(
        "Tiers cold data from the managed performance tier to low-cost object "
        "storage, substantially lowering NetApp-managed-file TCO."
    ),
)

with st.expander("Customer discovery (optional — shapes the recommendation)"):
    st.caption(
        "Provide an SE-style picture of the customer. The more context you "
        "supply, the more the recommendation moves beyond a generic default."
    )
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        cloud_provider = st.selectbox(
            "Primary cloud footprint",
            ["(unspecified)", "aws", "azure", "gcp", "multi"],
            help="Existing/target cloud. Steers toward native services.",
        )
        performance_tier = st.selectbox(
            "Performance posture", ["standard", "high", "archive"]
        )
    with dc2:
        budget_sensitivity = st.selectbox(
            "Priority", ["balanced", "cost", "performance"]
        )
        compliance_raw = st.text_input(
            "Compliance regimes (comma-separated)",
            placeholder="e.g. fedramp, hipaa",
        )
    with dc3:
        existing_netapp_ela = st.checkbox("Existing NetApp ELA / BYOL")
        cloud_exit_optionality = st.checkbox("Cloud-exit optionality matters")
    fc1, fc2 = st.columns(2)
    with fc1:
        provisioned_throughput_mbps = st.number_input(
            "Sustained throughput to provision (MBps, 0 = n/a)",
            min_value=0,
            value=0,
            step=100,
            help="Adds performance cost for throughput-billed services (FSxN, CVO).",
        )
    with fc2:
        on_prem_annual_usd = st.number_input(
            "Current on-prem annual storage spend (USD, 0 = unknown)",
            min_value=0,
            value=0,
            step=10_000,
            help=(
                "Enables the % TCO-reduction business case vs the customer's "
                "current spend."
            ),
        )
    milestones_raw = st.text_area(
        "Migration milestones (one per line)",
        height=80,
        placeholder=(
            "Discovery — Q3 2026\nPilot — Q4 2026\nCutover — by March 2027"
        ),
        help=(
            "The customer's stated dates. The plan's phase schedule is aligned "
            "to these instead of a generic 12-week template. Milestones found in "
            "the notes or uploaded artifacts are picked up automatically."
        ),
    )
    extra_context = st.text_area(
        "Additional context (pain points, constraints, success criteria)",
        height=80,
        placeholder="Free-form notes the agents should weigh.",
    )
    uploaded = st.file_uploader(
        "Upload artifacts (RFPs, assessments, monitoring exports) — PDF/CSV/TXT/MD",
        type=["pdf", "csv", "txt", "md", "log", "json"],
        accept_multiple_files=True,
        help=(
            "Text is extracted and given to the agents. Diagrams/images are not "
            "read by the current model. Do not upload confidential data to the "
            "public demo — nothing is persisted, but it is sent to the model "
            "provider."
        ),
    )

run_clicked = st.button("Run analysis", type="primary", use_container_width=True)

# ── Pipeline metadata ───────────────────────────────────────────────────────────
_AGENT_STEPS = [
    (
        "requirements_analyst",
        "Requirements Analyst",
        "Parses customer context, compliance & milestones",
    ),
    (
        "storage_analyst",
        "Storage Analyst",
        "Models capacity, dedup, workload segments",
    ),
    (
        "cloud_cost_estimator",
        "Cloud Cost Estimator",
        "Prices targets per segment, builds TCO case",
    ),
    (
        "migration_architect",
        "Migration Architect",
        "Drafts milestone-aligned migration plan",
    ),
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _collect_typed_outputs(result):
    """Pull the typed task outputs (StorageAnalysis, CustomerContext) if present."""
    analysis, discovered = None, None
    for task_out in getattr(result, "tasks_output", []) or []:
        pyd = getattr(task_out, "pydantic", None)
        if pyd is None:
            continue
        if hasattr(pyd, "effective_capacity_tb"):
            analysis = pyd
        elif hasattr(pyd, "milestones"):
            discovered = pyd
    return analysis, discovered


def _structured_report(result, form_ctx, tiering):
    """Re-run the deterministic engine with the analysts' structured output so the
    metric cards, tables, and charts use exact numbers (not regex-scraped prose).
    Uses the segmented engine when the analyst identified workload segments.
    Returns the report dict, or None if the structured analysis can't be recovered."""
    try:
        analysis, discovered = _collect_typed_outputs(result)
        if analysis is None:
            return None

        milestones = list(form_ctx.get("milestones") or [])
        if discovered is not None:
            for item in getattr(discovered, "milestones", None) or []:
                text = str(item or "").strip()
                if text and text not in milestones:
                    milestones.append(text)

        common = dict(
            enable_tiering=tiering,
            context=scoring.context_from_dict(form_ctx),
            provisioned_throughput_mbps=float(
                form_ctx.get("provisioned_throughput_mbps", 0) or 0
            ),
            on_prem_annual_usd=float(form_ctx.get("on_prem_annual_usd", 0) or 0),
            milestones=milestones,
        )

        segments = [s.model_dump() for s in getattr(analysis, "segments", None) or []]
        if segments:
            report = pricing.build_segmented_report(
                segments,
                default_hot_percent=float(analysis.hot_data_percent),
                default_growth_percent=float(analysis.growth_rate_percent),
                **common,
            )
            if report is not None:
                return report

        return pricing.build_report(
            raw_or_used_tb=float(analysis.effective_capacity_tb),
            dedup_ratio=1.0,
            hot_percent=float(analysis.hot_data_percent),
            annual_growth_percent=float(analysis.growth_rate_percent),
            file_protocol_required=bool(analysis.needs_file_protocol),
            **common,
        )
    except Exception:  # noqa: BLE001 - visualization is best-effort, never fatal
        return None


def _metric_cards_html(report: dict) -> str:
    rec = report["recommended_provider"]
    tco = report["three_year_tco_recommended_usd"]
    eff = report["effective_capacity_after_dedup_tb"]
    bc = report.get("business_case", {})
    segmented = report.get("segmented", False)
    rec_class = "mc-value small" if len(str(rec)) > 22 else "mc-value"
    rec_sub = "per-workload placement" if segmented else "best cost-and-fit score"
    cards = [
        f'<div class="metric-card"><div class="mc-label">Recommended</div>'
        f'<div class="{rec_class}">{rec}</div>'
        f'<div class="mc-sub">{rec_sub}</div></div>',
        f'<div class="metric-card"><div class="mc-label">3-Year TCO</div>'
        f'<div class="mc-value">${tco:,.0f}</div>'
        f'<div class="mc-sub">recommended solution</div></div>',
    ]
    if bc.get("baseline_provided"):
        pct = bc["tco_reduction_percent"]
        meets = (
            '<span class="ok">meets target</span>'
            if bc["meets_target"]
            else '<span class="warn">below target</span>'
        )
        cards.append(
            f'<div class="metric-card"><div class="mc-label">TCO Reduction</div>'
            f'<div class="mc-value">{pct:.0f}%</div>'
            f'<div class="mc-sub">vs current spend · {meets}</div></div>'
        )
    seg_sub = (
        f'{len(report["segments"])} workload segments'
        if segmented
        else "after dedup/compression"
    )
    cards.append(
        f'<div class="metric-card"><div class="mc-label">Effective Capacity</div>'
        f'<div class="mc-value">{eff:,.0f} TB</div>'
        f'<div class="mc-sub">{seg_sub}</div></div>'
    )
    return f'<div class="metric-row">{"".join(cards)}</div>'


def _segment_table_html(report: dict) -> str:
    """Per-segment placement table for segmented reports."""
    rows = []
    for seg in report["segments"]:
        badge = f'<span class="type-badge type-{seg["workload_type"]}">{seg["workload_type"]}</span>'
        rows.append(
            f"<tr><td>{seg['name']}</td><td>{badge}</td>"
            f'<td class="num">{seg["capacity_tb"]:,.0f} TB</td>'
            f'<td class="num">{seg["hot_percent"]:.0f}%</td>'
            f"<td>{seg['recommended_provider']}</td>"
            f'<td class="num">${seg["three_year_tco_usd"]:,.0f}</td></tr>'
        )
    combined = report["combined"]
    rows.append(
        f'<tr><td style="font-weight:600">Combined strategy</td><td></td>'
        f'<td class="num" style="font-weight:600">'
        f"{report['effective_capacity_after_dedup_tb']:,.0f} TB</td><td></td>"
        f'<td style="font-weight:600">{combined["strategy_label"]}</td>'
        f'<td class="num" style="font-weight:600">'
        f"${combined['mixed_three_year_tco_usd']:,.0f}</td></tr>"
    )
    return (
        '<table class="ent-table"><thead><tr>'
        "<th>Segment</th><th>Type</th>"
        '<th class="num">Effective</th><th class="num">Hot</th>'
        '<th>Recommended target</th><th class="num">3-yr TCO</th>'
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _timeline_table_html(schedule: dict) -> str:
    rows = []
    for phase in schedule.get("phases", []):
        anchor = phase.get("anchored_to")
        anchor_html = (
            f'<span class="anchor-note">{anchor}</span>'
            if anchor
            else '<span class="anchor-note">—</span>'
        )
        rows.append(
            f"<tr><td>{phase['phase']}</td><td>{phase['window']}</td>"
            f"<td>{anchor_html}</td></tr>"
        )
    return (
        '<table class="ent-table"><thead><tr>'
        "<th>Phase</th><th>Window</th><th>Alignment</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _tco_chart(entry: dict, height: int = 260):
    """Horizontal bar of 3-year TCO by provider, recommended highlighted.
    Works for both a blended report and a single segment entry."""
    rec = entry["recommended_provider"]
    rows = []
    for opt in entry["ranked_options"]:
        label = opt["provider"]
        if not opt.get("eligible", True):
            label += "  (ineligible)"
        rows.append(
            {
                "Provider": label,
                "TCO": opt["horizon_tco_usd"],
                "Pick": "Recommended" if opt["provider"] == rec else "Alternative",
            }
        )
    df = pd.DataFrame(rows)
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=3, height=20)
        .encode(
            x=alt.X("TCO:Q", title="3-Year TCO (USD)", axis=alt.Axis(format="$,.0f")),
            y=alt.Y(
                "Provider:N",
                sort=alt.EncodingSortField("TCO", order="ascending"),
                title=None,
            ),
            color=alt.Color(
                "Pick:N",
                scale=alt.Scale(
                    domain=["Recommended", "Alternative"],
                    range=[ACCENT, MUTED_BAR],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                "Provider",
                alt.Tooltip("TCO:Q", format="$,.0f", title="3-Year TCO"),
            ],
        )
        .properties(height=height)
    )


def _render_assumptions(report: dict) -> None:
    assumptions = report.get("assumptions", {})
    if not assumptions:
        return
    with st.expander("Assumptions & methodology"):
        lines = [
            f"- **Pricing basis:** {assumptions.get('pricing_as_of', '—')} public "
            f"list prices, {assumptions.get('region', '—')}; planning-grade "
            "estimates, not quotes.",
            "- **Sizing:** effective (post-dedup/compression) capacity; TCO "
            "compounds growth month-by-month over the horizon.",
        ]
        if "segments" in assumptions:
            lines.append(
                "- **Segments:** " + "; ".join(assumptions["segments"]) + "."
            )
            lines.append(
                f"- **Throughput:** {assumptions['throughput_apportionment']}."
            )
        else:
            lines.append(
                f"- **Access model:** {assumptions.get('hot_percent', '—')}% hot, "
                f"{assumptions.get('annual_growth_percent', '—')}% annual growth, "
                f"egress turnover {assumptions.get('egress_turnover_per_month', '—')}×/mo."
            )
        if assumptions.get("fabricpool_tiering_enabled"):
            lines.append(
                "- **FabricPool:** cold data on NetApp-managed targets tiered to "
                f"object storage at ${assumptions['fabricpool_capacity_tier_rate_per_gb']}/GB-mo."
            )
        lines.append(
            f"- **Not modeled:** {assumptions.get('excluded_from_model', '—')}"
        )
        st.markdown("\n".join(lines))


def _extract_metrics(text: str) -> dict:
    """Regex fallback for metric cards when structured data is unavailable."""
    metrics = {}
    for pat in [
        r"(?:recommended?|top recommendation)[:\s*]*\*{0,2}([^\n*]+?)\*{0,2}\n",
        r"\*{1,2}([^\n*]{5,60})\*{1,2}[^\n]*(?:is|as) (?:the )?(?:recommended?|top|optimal)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            metrics["recommendation"] = m.group(1).strip().rstrip(".")
            break
    m = re.search(r"TCO[^\n]*?\$([\d,]+(?:\.\d+)?[KMk]?)", text, re.IGNORECASE)
    if m:
        metrics["tco"] = "$" + m.group(1).strip()
    m = re.search(
        r"(\d{1,3})\s*%\s*(?:TCO\s*)?(?:reduction|savings|cheaper|lower)",
        text,
        re.IGNORECASE,
    )
    if m:
        metrics["savings_pct"] = m.group(1) + "%"
    return metrics


def _split_sections(text: str) -> dict:
    """Split markdown output into named sections for the tabbed display."""
    sections = {"summary": [], "cost": [], "plan": [], "other": []}
    current = "other"
    cost_kw = re.compile(
        r"(?:cost|tco|pricing|price|financial|budget|spend|savings?|roi|segments?)",
        re.I,
    )
    plan_kw = re.compile(
        r"(?:migration plan|phases?|roadmap|timeline|steps?|approach|implementation)",
        re.I,
    )
    summary_kw = re.compile(
        r"(?:executive summary|overview|summary|recommendation|conclusion)", re.I
    )
    for line in text.splitlines():
        heading = re.match(r"^#{1,3}\s+(.+)", line)
        if heading:
            title = heading.group(1)
            if summary_kw.search(title):
                current = "summary"
            elif cost_kw.search(title):
                current = "cost"
            elif plan_kw.search(title):
                current = "plan"
            else:
                current = "other"
        sections[current].append(line)

    def _join(key: str) -> str:
        return "\n".join(sections[key]).strip()

    return {
        "summary": _join("summary") or _join("other"),
        "cost": _join("cost"),
        "plan": _join("plan"),
        "full": text,
    }


def _agent_progress_html(active_index: int) -> str:
    rows = []
    for i, (_, name, desc) in enumerate(_AGENT_STEPS):
        if i < active_index:
            state = "done"
        elif i == active_index:
            state = "running"
        else:
            state = "pending"
        rows.append(
            f'<div class="agent-step"><div class="agent-dot {state}"></div>'
            f'<span class="agent-name {state}">{name}</span>'
            f'<span style="font-size:0.76rem;color:#94a3b8;margin-left:4px">— {desc}</span>'
            f"</div>"
        )
    return "\n".join(rows)


# ── Run ───────────────────────────────────────────────────────────────────────
if run_clicked:
    milestones = [line.strip() for line in milestones_raw.splitlines() if line.strip()]
    context = {
        "cloud_provider": "" if cloud_provider == "(unspecified)" else cloud_provider,
        "performance_tier": performance_tier,
        "budget_sensitivity": budget_sensitivity,
        "existing_netapp_ela": existing_netapp_ela,
        "cloud_exit_optionality": cloud_exit_optionality,
        "compliance": [c.strip() for c in compliance_raw.split(",") if c.strip()],
        "provisioned_throughput_mbps": provisioned_throughput_mbps,
        "on_prem_annual_usd": on_prem_annual_usd,
        "milestones": milestones,
    }
    profile = workload_profile
    if extra_context.strip():
        profile = f"{workload_profile}\n\nAdditional context: {extra_context.strip()}"
    if uploaded:
        files = [(f.name, f.getvalue()) for f in uploaded]
        artifact_text = artifacts.combine_artifacts(files)
        if artifact_text:
            profile = f"{profile}\n\n{artifact_text}"

    inputs = {
        "storage_config": storage_config,
        "workload_profile": profile,
        "enable_tiering": enable_tiering,
        "customer_context_json": json.dumps(context),
    }

    try:
        validate_environment(os.getenv("MODEL", DEFAULT_MODEL))
    except ConfigError as exc:
        st.warning(str(exc))
        st.stop()

    progress_placeholder = st.empty()

    def _show_progress(step: int) -> None:
        progress_placeholder.markdown(
            f'<div class="panel">'
            f'<div class="section-label">Agent pipeline · step {step + 1} of {len(_AGENT_STEPS)}</div>'
            f"{_agent_progress_html(step)}"
            f"</div>",
            unsafe_allow_html=True,
        )

    _show_progress(0)
    result_container = [None]
    error_container = [None]

    try:
        crew_obj = HybridCloudStorageOptimizer().crew()

        # Advance the progress display as each task completes (chaining any
        # callback the crew itself registered, e.g. the typed-output stashing).
        for i, task in enumerate(crew_obj.tasks):
            original_cb = getattr(task, "callback", None)

            def _make_cb(idx, orig):
                def _cb(output):
                    _show_progress(min(idx + 1, len(_AGENT_STEPS) - 1))
                    if orig:
                        orig(output)

                return _cb

            task.callback = _make_cb(i, original_cb)

        result = crew_obj.kickoff(inputs=inputs)
        result_container[0] = result
    except Exception as exc:  # noqa: BLE001
        error_container[0] = exc

    progress_placeholder.empty()

    if error_container[0]:
        st.error(friendly_error(error_container[0]))
        st.stop()

    raw_text = clean_output(str(result_container[0]))
    report = _structured_report(result_container[0], context, enable_tiering)

    # ── Metric cards (structured if available, regex fallback otherwise) ────────
    if report:
        st.markdown(_metric_cards_html(report), unsafe_allow_html=True)
    else:
        metrics = _extract_metrics(raw_text)
        cards = ""
        if metrics.get("recommendation"):
            cards += (
                f'<div class="metric-card"><div class="mc-label">Recommended</div>'
                f'<div class="mc-value small">{metrics["recommendation"]}</div></div>'
            )
        if metrics.get("tco"):
            cards += (
                f'<div class="metric-card"><div class="mc-label">3-Year TCO</div>'
                f'<div class="mc-value">{metrics["tco"]}</div></div>'
            )
        if metrics.get("savings_pct"):
            cards += (
                f'<div class="metric-card"><div class="mc-label">TCO Reduction</div>'
                f'<div class="mc-value">{metrics["savings_pct"]}</div></div>'
            )
        if cards:
            st.markdown(
                f'<div class="metric-row">{cards}</div>', unsafe_allow_html=True
            )

    st.success("Analysis complete — review the sections below.")

    # ── Tabbed results ──────────────────────────────────────────────────────────
    sections = _split_sections(raw_text)
    tabs = st.tabs(
        [
            "Summary & Recommendation",
            "Cost Analysis",
            "Migration Plan",
            "Full Report",
        ]
    )

    with tabs[0]:
        if report and report.get("segmented"):
            st.markdown(
                '<div class="section-label">Workload placement</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_segment_table_html(report), unsafe_allow_html=True)
            single = report["combined"].get("single_provider_alternative")
            if single:
                delta = single["delta_vs_mixed_usd"]
                direction = "premium" if delta >= 0 else "saving"
                st.caption(
                    f"Consolidation alternative: {single['provider']} for every "
                    f"segment at ${single['three_year_tco_usd']:,.0f} 3-yr TCO — a "
                    f"${abs(delta):,.0f} {direction} vs the per-segment mix, "
                    "traded against operating a single platform."
                )
        st.markdown(sections["summary"] or raw_text)

    with tabs[1]:
        if report and report.get("segmented"):
            for seg in report["segments"]:
                st.markdown(
                    f'<div class="section-label">{seg["name"]} · '
                    f'{seg["workload_type"]} · {seg["capacity_tb"]:,.0f} TB → '
                    f'{seg["recommended_provider"]} '
                    f'(${seg["three_year_tco_usd"]:,.0f})</div>',
                    unsafe_allow_html=True,
                )
                st.altair_chart(
                    _tco_chart(seg, height=210), use_container_width=True
                )
                if seg["excluded_options"]:
                    note = "; ".join(
                        f"{e['provider']} ({e['reason']})"
                        for e in seg["excluded_options"]
                    )
                    st.caption(f"Excluded for this segment: {note}.")
        elif report:
            st.markdown(
                '<div class="section-label">3-Year TCO by provider</div>',
                unsafe_allow_html=True,
            )
            st.altair_chart(_tco_chart(report), use_container_width=True)
            excluded = report.get("excluded_options", [])
            if excluded:
                note = "; ".join(f"{e['provider']} ({e['reason']})" for e in excluded)
                st.caption(f"Excluded from the recommendation: {note}.")
        if report:
            _render_assumptions(report)
        if sections["cost"]:
            st.markdown(sections["cost"])
        elif not report:
            st.info("Cost breakdown is embedded in the Full Report tab.")

    with tabs[2]:
        schedule = (report or {}).get("migration_timeline")
        if schedule:
            st.markdown(
                '<div class="section-label">Phase schedule</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_timeline_table_html(schedule), unsafe_allow_html=True)
            if schedule.get("source") == "customer_milestones":
                st.caption(schedule.get("summary", ""))
            else:
                st.caption(
                    "Standard 12-week template — no customer milestones were "
                    "provided. Add milestones in Customer discovery to align the "
                    "schedule to the customer's calendar."
                )
            for conflict in schedule.get("conflicts", []):
                st.warning(f"Timeline conflict: {conflict}")
            unparsed = schedule.get("unparsed_milestones", [])
            if unparsed:
                st.caption(
                    "Could not interpret as dates: " + "; ".join(unparsed) + "."
                )
        st.markdown(sections["plan"] or "Migration plan is in the Full Report tab.")

    with tabs[3]:
        st.markdown(raw_text)

    st.download_button(
        label="Download full report (.md)",
        data=raw_text,
        file_name="hybrid_cloud_storage_analysis.md",
        mime="text/markdown",
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
<div class="app-footer">
Estimates are computed by a deterministic TCO engine from public {pricing.PRICING_AS_OF}
list prices ({pricing.PRICING_REGION}) and documented assumptions — planning guidance,
not a quote. Recommendations weigh protocol eligibility, cloud footprint, performance,
compliance, licensing, and strategy alongside cost.<br>
Multi-agent analysis: CrewAI · Groq Llama 3.3 70B · deterministic pricing, scoring,
segmentation & timeline engines.
</div>
""",
    unsafe_allow_html=True,
)
