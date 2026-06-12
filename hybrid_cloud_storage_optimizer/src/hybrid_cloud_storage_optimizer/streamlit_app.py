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
from hybrid_cloud_storage_optimizer.tools import (
    artifacts,
    pricing,
    scoring,
)  # noqa: E402

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hybrid Cloud Storage Optimizer",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS — vibrant gradient SaaS ──────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stMarkdown, .stTextArea, .stSelectbox, .stTextInput {
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
}
.block-container { padding-top: 2rem; max-width: 1180px; }

/* ── Hero ── */
.hero {
    background: linear-gradient(120deg, #4f46e5 0%, #7c3aed 45%, #2563eb 100%);
    border-radius: 22px;
    padding: 2.6rem 2.8rem 2.2rem;
    margin-bottom: 1.8rem;
    color: white;
    box-shadow: 0 18px 45px -18px rgba(79, 70, 229, 0.65);
    position: relative;
    overflow: hidden;
}
.hero::after {
    content: "";
    position: absolute; top: -40%; right: -10%;
    width: 380px; height: 380px; border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,0.18), transparent 70%);
}
.hero h1 { font-size: 2.4rem; font-weight: 800; margin: 0 0 0.4rem; color: white; letter-spacing: -0.02em; }
.hero p  { font-size: 1.05rem; opacity: 0.92; margin: 0; color: white; font-weight: 400; }
.hero .badges { margin-top: 1rem; }
.hero .pill {
    display: inline-block;
    background: rgba(255,255,255,0.16);
    backdrop-filter: blur(6px);
    border: 1px solid rgba(255,255,255,0.22);
    border-radius: 30px;
    padding: 4px 14px; font-size: 0.78rem; font-weight: 500;
    margin-right: 8px; margin-top: 8px; color: white;
}

/* ── Section labels ── */
.section-label {
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.1em; color: #7c3aed; margin: 0.5rem 0 0.7rem;
}

/* ── Metric cards ── */
.metric-row { display: flex; gap: 1rem; margin: 0.5rem 0 1.5rem; flex-wrap: wrap; }
.metric-card {
    flex: 1; min-width: 175px;
    background: white;
    border: 1px solid #ede9fe;
    border-radius: 16px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 10px 30px -20px rgba(79,70,229,0.5);
    position: relative; overflow: hidden;
}
.metric-card::before {
    content: ""; position: absolute; top: 0; left: 0; height: 100%; width: 5px;
    background: linear-gradient(180deg, #6d28d9, #2563eb);
}
.metric-card.green::before  { background: linear-gradient(180deg, #16a34a, #22c55e); }
.metric-card.orange::before { background: linear-gradient(180deg, #ea580c, #f59e0b); }
.metric-card.blue::before   { background: linear-gradient(180deg, #2563eb, #06b6d4); }
.metric-card .mc-label { font-size: 0.7rem; color: #8b8a9b; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
.metric-card .mc-value { font-size: 1.7rem; font-weight: 800; color: #1e1b2e; line-height: 1.15; margin-top: 4px; }
.metric-card .mc-sub   { font-size: 0.75rem; color: #8b8a9b; margin-top: 3px; }

/* ── Agent progress ── */
.section-card {
    background: #faf9ff; border: 1px solid #ede9fe; border-radius: 16px;
    padding: 1.3rem 1.6rem; margin-bottom: 1rem;
}
.agent-step { display: flex; align-items: center; gap: 0.6rem; padding: 0.5rem 0; }
.agent-dot  { width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }
.agent-dot.done    { background: #16a34a; }
.agent-dot.running { background: #7c3aed; animation: pulse 1.2s infinite; }
.agent-dot.pending { background: #d8d4f0; }
@keyframes pulse { 0%,100% { opacity: 1; transform: scale(1);} 50% { opacity: 0.4; transform: scale(1.25);} }
.agent-name { font-size: 0.88rem; color: #4b4860; }
.agent-name.done    { color: #15803d; }
.agent-name.running { color: #6d28d9; font-weight: 700; }
.agent-name.pending { color: #a8a4c0; }

/* ── Primary button ── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(120deg, #6d28d9, #4f46e5 60%, #2563eb);
    border: none; border-radius: 12px; font-weight: 700; font-size: 1rem;
    padding: 0.7rem 1rem; box-shadow: 0 12px 28px -12px rgba(79,70,229,0.7);
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-2px); box-shadow: 0 16px 34px -12px rgba(79,70,229,0.8);
}

/* ── Tabs ── */
div[data-testid="stTabs"] button { font-weight: 600; font-size: 0.9rem; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: #6d28d9; }
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: #6d28d9; }

/* ── Download button ── */
div[data-testid="stDownloadButton"] button {
    background: #f5f3ff; border: 1px solid #ddd6fe; color: #5b21b6;
    border-radius: 10px; font-weight: 600; font-size: 0.84rem;
}

/* ── Footer ── */
.app-footer {
    text-align: center; font-size: 0.74rem; color: #a8a4c0;
    margin-top: 2.2rem; padding-top: 1.1rem; border-top: 1px solid #ede9fe;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="hero">
  <h1>☁️ Hybrid Cloud Storage Optimizer</h1>
  <p>AI migration advisor for NetApp ONTAP → Cloud · deterministic 2026 TCO across 6 providers</p>
  <div class="badges">
    <span class="pill">⚡ CrewAI multi-agent</span>
    <span class="pill">📊 Deterministic pricing</span>
    <span class="pill">🛡️ Compliance-aware</span>
    <span class="pill">🧊 FabricPool tiering</span>
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
        "Storage Configuration",
        value=(
            "ONTAP cluster with 500TB FAS, 70% utilization, "
            "heavy NFS workloads, dedup ratio 2:1"
        ),
        height=110,
    )
with col2:
    workload_profile = st.text_area(
        "Workload Profile",
        value=(
            "Mixed hot/cold data, frequent access to 20%, "
            "archival 80%, expected 15% annual growth"
        ),
        height=110,
    )

enable_tiering = st.checkbox(
    "Apply NetApp FabricPool cold-tiering to managed-file options",
    value=True,
    help=(
        "Tiers cold data from the managed performance tier to low-cost object "
        "storage, substantially lowering NetApp-managed-file TCO."
    ),
)

with st.expander("🧭 Customer Discovery  (optional — shapes the recommendation)"):
    st.caption(
        "Provide an SE-style picture of the customer. "
        "The more context you supply, the more the recommendation moves beyond a "
        "generic default."
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
            "read by the current model. Do not upload confidential data to the public "
            "demo — nothing is persisted, but it is sent to the model provider."
        ),
    )

run_clicked = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

# ── Pipeline metadata ───────────────────────────────────────────────────────────
_AGENT_STEPS = [
    (
        "requirements_analyst",
        "Requirements Analyst",
        "Parses customer & compliance context",
    ),
    ("storage_analyst", "Storage Analyst", "Models capacity, dedup, hot/cold split"),
    (
        "cloud_cost_estimator",
        "Cloud Cost Estimator",
        "Prices 6 targets, builds TCO table",
    ),
    ("migration_architect", "Migration Architect", "Drafts phased migration plan"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _structured_report(result, form_ctx, tiering):
    """Re-run the deterministic engine with the analyst's structured output so the
    metric cards and chart use exact numbers (not regex-scraped prose). Returns the
    build_report dict, or None if the structured analysis can't be recovered."""
    try:
        analysis = None
        for task_out in getattr(result, "tasks_output", []) or []:
            pyd = getattr(task_out, "pydantic", None)
            if pyd is not None and hasattr(pyd, "effective_capacity_tb"):
                analysis = pyd
                break
        if analysis is None:
            return None
        return pricing.build_report(
            raw_or_used_tb=float(analysis.effective_capacity_tb),
            dedup_ratio=1.0,
            hot_percent=float(analysis.hot_data_percent),
            annual_growth_percent=float(analysis.growth_rate_percent),
            file_protocol_required=bool(analysis.needs_file_protocol),
            enable_tiering=tiering,
            context=scoring.context_from_dict(form_ctx),
            provisioned_throughput_mbps=float(
                form_ctx.get("provisioned_throughput_mbps", 0) or 0
            ),
            on_prem_annual_usd=float(form_ctx.get("on_prem_annual_usd", 0) or 0),
        )
    except Exception:  # noqa: BLE001 - visualization is best-effort, never fatal
        return None


def _metric_cards_html(report: dict) -> str:
    rec = report["recommended_provider"]
    tco = report["three_year_tco_recommended_usd"]
    eff = report["effective_capacity_after_dedup_tb"]
    bc = report.get("business_case", {})
    cards = [
        f'<div class="metric-card"><div class="mc-label">Recommended</div>'
        f'<div class="mc-value" style="font-size:1.2rem">{rec}</div>'
        f'<div class="mc-sub">best cost-and-fit score</div></div>',
        f'<div class="metric-card green"><div class="mc-label">3-Year TCO</div>'
        f'<div class="mc-value">${tco:,.0f}</div>'
        f'<div class="mc-sub">recommended solution</div></div>',
    ]
    if bc.get("baseline_provided"):
        pct = bc["tco_reduction_percent"]
        meets = "meets target ✓" if bc["meets_target"] else "below target"
        cards.append(
            f'<div class="metric-card orange"><div class="mc-label">TCO Reduction</div>'
            f'<div class="mc-value">{pct:.0f}%</div>'
            f'<div class="mc-sub">vs current spend · {meets}</div></div>'
        )
    cards.append(
        f'<div class="metric-card blue"><div class="mc-label">Effective Capacity</div>'
        f'<div class="mc-value">{eff:,.0f} TB</div>'
        f'<div class="mc-sub">after dedup/compression</div></div>'
    )
    return f'<div class="metric-row">{"".join(cards)}</div>'


def _tco_chart(report: dict):
    """Horizontal bar of 3-year TCO by provider, recommended highlighted."""
    rec = report["recommended_provider"]
    rows = []
    for opt in report["ranked_options"]:
        label = opt["provider"]
        if not opt.get("eligible", True):
            label += "  ⚠︎"  # ineligible (cloud/protocol) — shown but not picked
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
        .mark_bar(cornerRadiusEnd=7, height=22)
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
                    range=["#7c3aed", "#cbd5e1"],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                "Provider",
                alt.Tooltip("TCO:Q", format="$,.0f", title="3-Year TCO"),
            ],
        )
        .properties(height=300)
    )


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
        r"(?:cost|tco|pricing|price|financial|budget|spend|savings?|roi)", re.I
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
            state, icon = "done", "✓"
        elif i == active_index:
            state, icon = "running", "▶"
        else:
            state, icon = "pending", "○"
        rows.append(
            f'<div class="agent-step"><div class="agent-dot {state}"></div>'
            f'<span class="agent-name {state}">{icon} {name}</span>'
            f'<span style="font-size:0.76rem;color:#a8a4c0;margin-left:4px">— {desc}</span>'
            f"</div>"
        )
    return "\n".join(rows)


# ── Run ───────────────────────────────────────────────────────────────────────
if run_clicked:
    context = {
        "cloud_provider": "" if cloud_provider == "(unspecified)" else cloud_provider,
        "performance_tier": performance_tier,
        "budget_sensitivity": budget_sensitivity,
        "existing_netapp_ela": existing_netapp_ela,
        "cloud_exit_optionality": cloud_exit_optionality,
        "compliance": [c.strip() for c in compliance_raw.split(",") if c.strip()],
        "provisioned_throughput_mbps": provisioned_throughput_mbps,
        "on_prem_annual_usd": on_prem_annual_usd,
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
            f'<div class="section-card">'
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

        # Advance the progress display as each task completes.
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
                f'<div class="mc-value" style="font-size:1.2rem">{metrics["recommendation"]}</div></div>'
            )
        if metrics.get("tco"):
            cards += (
                f'<div class="metric-card green"><div class="mc-label">3-Year TCO</div>'
                f'<div class="mc-value">{metrics["tco"]}</div></div>'
            )
        if metrics.get("savings_pct"):
            cards += (
                f'<div class="metric-card orange"><div class="mc-label">TCO Reduction</div>'
                f'<div class="mc-value">{metrics["savings_pct"]}</div></div>'
            )
        if cards:
            st.markdown(
                f'<div class="metric-row">{cards}</div>', unsafe_allow_html=True
            )

    st.success("✅ Analysis complete — review the sections below.")

    # ── Tabbed results ──────────────────────────────────────────────────────────
    sections = _split_sections(raw_text)
    tabs = st.tabs(
        [
            "📋 Summary & Recommendation",
            "💰 Cost Analysis",
            "🗺️ Migration Plan",
            "📄 Full Report",
        ]
    )

    with tabs[0]:
        st.markdown(sections["summary"] or raw_text)

    with tabs[1]:
        if report:
            st.markdown(
                '<div class="section-label">3-Year TCO by provider</div>',
                unsafe_allow_html=True,
            )
            st.altair_chart(_tco_chart(report), use_container_width=True)
            excluded = report.get("excluded_options", [])
            if excluded:
                note = "; ".join(f"{e['provider']} ({e['reason']})" for e in excluded)
                st.caption(f"Excluded from the recommendation: {note}.")
        if sections["cost"]:
            st.markdown(sections["cost"])
        elif not report:
            st.info("Cost breakdown is embedded in the Full Report tab.")

    with tabs[2]:
        st.markdown(sections["plan"] or "Migration plan is in the Full Report tab.")

    with tabs[3]:
        st.markdown(raw_text)

    st.download_button(
        label="⬇️ Download full report (.md)",
        data=raw_text,
        file_name="hybrid_cloud_storage_analysis.md",
        mime="text/markdown",
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="app-footer">Built with CrewAI · Groq · NetApp domain expertise</div>',
    unsafe_allow_html=True,
)
