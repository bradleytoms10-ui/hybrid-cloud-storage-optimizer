import json
import os
import re
import sys
from pathlib import Path

# Make the package importable when run directly (e.g. Streamlit Community Cloud,
# which does not pip-install the local project). src/ is two levels up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
from hybrid_cloud_storage_optimizer.tools import artifacts  # noqa: E402

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hybrid Cloud Storage Optimizer",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Brand header ── */
.brand-header {
    background: linear-gradient(135deg, #0f2842 0%, #1a4a7a 60%, #0078d4 100%);
    border-radius: 12px;
    padding: 2rem 2.5rem 1.5rem;
    margin-bottom: 1.5rem;
    color: white;
}
.brand-header h1 { font-size: 2rem; font-weight: 700; margin: 0 0 0.25rem; color: white; }
.brand-header p  { font-size: 1rem; opacity: 0.85; margin: 0; color: white; }
.brand-badge {
    display: inline-block;
    background: rgba(255,255,255,0.15);
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.75rem;
    margin-right: 6px;
    margin-top: 10px;
    color: white;
}

/* ── Section cards ── */
.section-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}
.section-label {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #64748b;
    margin-bottom: 0.6rem;
}

/* ── Metric callout ── */
.metric-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.25rem;
    flex-wrap: wrap;
}
.metric-card {
    flex: 1;
    min-width: 160px;
    background: white;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #0078d4;
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
}
.metric-card.green  { border-left-color: #16a34a; }
.metric-card.orange { border-left-color: #ea580c; }
.metric-card.purple { border-left-color: #7c3aed; }
.metric-card .mc-label { font-size: 0.72rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.metric-card .mc-value { font-size: 1.5rem; font-weight: 700; color: #0f172a; line-height: 1.2; margin-top: 2px; }
.metric-card .mc-sub   { font-size: 0.75rem; color: #64748b; margin-top: 2px; }

/* ── Agent progress ── */
.agent-step { display: flex; align-items: center; gap: 0.6rem; padding: 0.45rem 0; }
.agent-dot  { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.agent-dot.done    { background: #16a34a; }
.agent-dot.running { background: #0078d4; animation: pulse 1.2s infinite; }
.agent-dot.pending { background: #cbd5e1; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
.agent-name { font-size: 0.85rem; color: #334155; }
.agent-name.done    { color: #15803d; }
.agent-name.running { color: #0078d4; font-weight: 600; }
.agent-name.pending { color: #94a3b8; }

/* ── Result tabs ── */
div[data-testid="stTabs"] button { font-weight: 600; font-size: 0.85rem; }

/* ── Download button ── */
div[data-testid="stDownloadButton"] button {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    color: #334155;
    font-size: 0.82rem;
}

/* ── Footer ── */
.app-footer {
    text-align: center;
    font-size: 0.72rem;
    color: #94a3b8;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid #e2e8f0;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="brand-header">
  <h1>☁️ Hybrid Cloud Storage Optimizer</h1>
  <p>AI-powered migration advisor · NetApp ONTAP → Cloud · 2026 TCO engine</p>
  <span class="brand-badge">CrewAI multi-agent</span>
  <span class="brand-badge">6 cloud providers</span>
  <span class="brand-badge">Deterministic pricing</span>
  <span class="brand-badge">Compliance-aware</span>
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
        label_visibility="visible",
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

# ── Helpers ───────────────────────────────────────────────────────────────────
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

_PROVIDER_LABELS = {
    "fsx": "FSx for ONTAP",
    "fsxn": "FSx for ONTAP",
    "cvo": "NetApp CVO",
    "anf": "Azure NetApp Files",
    "azure netapp": "Azure NetApp Files",
    "aws s3": "AWS S3",
    "azure blob": "Azure Blob",
    "google": "Google Cloud Storage",
    "gcs": "Google Cloud Storage",
}


def _extract_metrics(text: str) -> dict:
    """Pull headline numbers from the LLM output for the metric cards."""
    metrics = {}

    # Recommended solution — look for bold/heading near "recommend"
    for pat in [
        r"(?:recommended?|top recommendation)[:\s*]*\*{0,2}([^\n*]+?)\*{0,2}\n",
        r"#+ ?(?:recommended?|top)[^\n]*\n\*{0,2}([^\n*]+?)\*{0,2}",
        r"\*{1,2}([^\n*]{5,60})\*{1,2}[^\n]*(?:is|as) (?:the )?(?:recommended?|top|optimal)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            metrics["recommendation"] = m.group(1).strip().rstrip(".")
            break

    # 3-year TCO of recommended solution
    for pat in [
        r"(?:3.year|three.year)[^\n]*?TCO[^\n]*?\$([\d,]+(?:\.\d+)?[KMk]?)",
        r"\$([\d,]+(?:\.\d+)?[KMk]?)[^\n]*(?:3.year|three.year)[^\n]*TCO",
        r"TCO[^\n]*?\$([\d,]+(?:\.\d+)?[KMk]?)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            metrics["tco"] = "$" + m.group(1).strip()
            break

    # Savings % vs on-prem
    m = re.search(
        r"(\d{1,3})\s*%\s*(?:TCO\s*)?(?:reduction|savings|cheaper|lower)",
        text,
        re.IGNORECASE,
    )
    if m:
        metrics["savings_pct"] = m.group(1) + "%"

    # Payback / break-even months
    m = re.search(r"(\d+)\s*month[s]?\s*(?:payback|break.?even)", text, re.IGNORECASE)
    if m:
        metrics["payback"] = m.group(1) + " mo"

    return metrics


def _split_sections(text: str) -> dict[str, str]:
    """
    Split markdown output into named sections for the tabbed display.
    Returns keys: summary, cost, plan, full.
    """
    sections: dict[str, list[str]] = {
        "summary": [],
        "cost": [],
        "plan": [],
        "other": [],
    }
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

    summary_text = _join("summary") or _join("other")
    cost_text = _join("cost")
    plan_text = _join("plan")

    return {"summary": summary_text, "cost": cost_text, "plan": plan_text, "full": text}


def _agent_progress_html(active_index: int) -> str:
    rows = []
    for i, (_, name, desc) in enumerate(_AGENT_STEPS):
        if i < active_index:
            state = "done"
            icon = "✓"
        elif i == active_index:
            state = "running"
            icon = "▶"
        else:
            state = "pending"
            icon = "○"
        rows.append(
            f'<div class="agent-step">'
            f'<div class="agent-dot {state}"></div>'
            f'<span class="agent-name {state}">{icon} {name}</span>'
            f'<span style="font-size:0.75rem;color:#94a3b8;margin-left:4px">— {desc}</span>'
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

    # ── Agent progress display ────────────────────────────────────────────────
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

    # CrewAI runs synchronously; we update the progress indicator between tasks
    # by hooking the task callbacks on the crew object.
    result_container = [None]
    error_container = [None]

    # Patch: inject a step-advance callback via CrewAI task callbacks
    task_counter = [0]

    try:
        crew_obj = HybridCloudStorageOptimizer().crew()

        # Attach a callback to each task that advances the progress display
        for i, task in enumerate(crew_obj.tasks):
            step_index = i  # capture

            original_cb = getattr(task, "callback", None)

            def _make_cb(idx, orig):
                def _cb(output):
                    _show_progress(min(idx + 1, len(_AGENT_STEPS) - 1))
                    if orig:
                        orig(output)

                return _cb

            task.callback = _make_cb(step_index, original_cb)

        result = crew_obj.kickoff(inputs=inputs)
        result_container[0] = result
    except Exception as exc:  # noqa: BLE001
        error_container[0] = exc

    progress_placeholder.empty()

    if error_container[0]:
        st.error(friendly_error(error_container[0]))
        st.stop()

    raw_text = clean_output(str(result_container[0]))

    # ── Metric callout cards ──────────────────────────────────────────────────
    metrics = _extract_metrics(raw_text)

    cards_html = ""
    if metrics.get("recommendation"):
        cards_html += (
            f'<div class="metric-card">'
            f'<div class="mc-label">Top Recommendation</div>'
            f'<div class="mc-value" style="font-size:1.1rem">{metrics["recommendation"]}</div>'
            f"</div>"
        )
    if metrics.get("tco"):
        cards_html += (
            f'<div class="metric-card green">'
            f'<div class="mc-label">3-Year TCO</div>'
            f'<div class="mc-value">{metrics["tco"]}</div>'
            f'<div class="mc-sub">recommended solution</div>'
            f"</div>"
        )
    if metrics.get("savings_pct"):
        cards_html += (
            f'<div class="metric-card orange">'
            f'<div class="mc-label">TCO Reduction</div>'
            f'<div class="mc-value">{metrics["savings_pct"]}</div>'
            f'<div class="mc-sub">vs current on-prem spend</div>'
            f"</div>"
        )
    if metrics.get("payback"):
        cards_html += (
            f'<div class="metric-card purple">'
            f'<div class="mc-label">Payback Period</div>'
            f'<div class="mc-value">{metrics["payback"]}</div>'
            f"</div>"
        )

    if cards_html:
        st.markdown(
            f'<div class="metric-row">{cards_html}</div>',
            unsafe_allow_html=True,
        )

    # ── Success banner ────────────────────────────────────────────────────────
    st.success("✅ Analysis complete — review the sections below.")

    # ── Tabbed results ────────────────────────────────────────────────────────
    sections = _split_sections(raw_text)

    tab_labels = [
        "📋 Summary & Recommendation",
        "💰 Cost Analysis",
        "🗺️ Migration Plan",
        "📄 Full Report",
    ]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        if sections["summary"]:
            st.markdown(sections["summary"])
        else:
            st.markdown(raw_text)

    with tabs[1]:
        if sections["cost"]:
            st.markdown(sections["cost"])
        else:
            st.info("Cost breakdown is embedded in the Full Report tab.")

    with tabs[2]:
        if sections["plan"]:
            st.markdown(sections["plan"])
        else:
            st.info("Migration plan is embedded in the Full Report tab.")

    with tabs[3]:
        st.markdown(raw_text)

    # ── Download ──────────────────────────────────────────────────────────────
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
