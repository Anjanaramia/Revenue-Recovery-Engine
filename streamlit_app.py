"""
streamlit_app.py
Main UI for the CRM Lead Reactivation Engine.
5-tab layout: Upload & Clean | Score & Prioritize | Outreach Generator | Client Dashboard | Monthly Report
"""

import streamlit as st
# ── EMAIL GATE ──────────────────────────────────────
import re

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

if "access_granted" not in st.session_state:
    st.session_state.access_granted = False

if not st.session_state.access_granted:
    st.markdown("## 🚀 AG Lead Reactivation Engine")
    st.markdown("**Turn your dormant leads into closed deals — free for real estate agents.**")
    st.divider()
    
    email = st.text_input("Enter your email to access the engine:")
    name  = st.text_input("Your name (optional):")
    
    if st.button("Get Free Access"):
        if is_valid_email(email):
            # Save to a local CSV log
            import csv, os
            from datetime import datetime
            log_file = "leads_captured.csv"
            file_exists = os.path.isfile(log_file)
            with open(log_file, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp","name","email"])
                if not file_exists:
                    writer.writeheader()
                writer.writerow({
                    "timestamp": datetime.now().isoformat(),
                    "name": name,
                    "email": email
                })
            st.session_state.access_granted = True
            st.rerun()
        else:
            st.error("Please enter a valid email address.")
    
    st.stop()  # Nothing below renders until access is granted
# ── END EMAIL GATE ───────────────────────────────────
import pandas as pd
import numpy as np
import os
from datetime import datetime, date

from data_cleaner import clean_crm_data, get_cleaned_export
from reactivation_engine import (
    score_leads, get_leads_by_temperature, get_buyer_seller_split,
    get_display_columns, DEFAULT_TIERS, TEMPERATURE_COLORS
)
from outreach_generator import generate_outreach_for_row
from client_manager import (
    init_db, get_all_clients, get_client_names, add_client, get_client_by_name,
    record_run, get_client_runs, get_last_run, get_or_create_monthly,
    upsert_monthly_tracking, get_year_month, delete_client, get_client_summary
)
from reporting import build_monthly_summary, export_report_csv, export_report_pdf, build_trend_dataframe

# ── Page Config ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AG Reactivation Engine",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Header gradient banner ── */
.app-header {
    background: linear-gradient(135deg, #1E3A5F 0%, #2C5F8A 50%, #1a8a5a 100%);
    padding: 1.5rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    color: white;
    box-shadow: 0 4px 20px rgba(30,58,95,0.3);
}
.app-header h1 { color: white; margin: 0; font-size: 1.8rem; font-weight: 700; }
.app-header p  { color: rgba(255,255,255,0.8); margin: 0.25rem 0 0; font-size: 0.9rem; }

/* ── Metric cards ── */
.metric-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    text-align: center;
}
.metric-card .label { font-size: 0.78rem; color: #64748b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
.metric-card .value { font-size: 1.8rem; font-weight: 700; color: #1E3A5F; margin-top: 0.2rem; }
.metric-card .delta { font-size: 0.75rem; margin-top: 0.1rem; }

/* ── Temperature badges ── */
.badge-hot     { background:#fee2e2; color:#991b1b; padding:3px 10px; border-radius:999px; font-weight:600; font-size:0.8rem; }
.badge-warm    { background:#fef9c3; color:#854d0e; padding:3px 10px; border-radius:999px; font-weight:600; font-size:0.8rem; }
.badge-cold    { background:#dbeafe; color:#1e40af; padding:3px 10px; border-radius:999px; font-weight:600; font-size:0.8rem; }
.badge-dormant { background:#f1f5f9; color:#334155; padding:3px 10px; border-radius:999px; font-weight:600; font-size:0.8rem; border:1px solid #94a3b8; }

/* ── Quality score bar ── */
.quality-bar-wrap { background:#e2e8f0; border-radius:999px; height:12px; margin:8px 0; }
.quality-bar-fill { height:12px; border-radius:999px; transition: width 0.5s; }

/* ── Section titles ── */
.section-title {
    font-size: 1.1rem; font-weight: 600; color: #1E3A5F;
    border-left: 4px solid #2ECC71;
    padding-left: 0.6rem; margin: 1.2rem 0 0.8rem;
}

/* ── Outreach card ── */
.outreach-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    font-size: 0.88rem;
    line-height: 1.6;
    white-space: pre-wrap;
    font-family: 'Inter', sans-serif;
}

/* ── Alert banner ── */
.alert-success { background:#dcfce7; border-left:4px solid #16a34a; padding:0.7rem 1rem; border-radius:6px; color:#166534; font-size:0.9rem; }
.alert-warning { background:#fef9c3; border-left:4px solid #ca8a04; padding:0.7rem 1rem; border-radius:6px; color:#854d0e; font-size:0.9rem; }
.alert-info    { background:#dbeafe; border-left:4px solid #2563eb; padding:0.7rem 1rem; border-radius:6px; color:#1e40af; font-size:0.9rem; }

/* ── Tab styling ── */
.stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
.stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 0.5rem 1rem; font-weight: 500; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] { background: #f8fafc; }
</style>
""", unsafe_allow_html=True)

# ── Initialize DB ────────────────────────────────────────────────────────────────
init_db()

# ── Session State Defaults ───────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "raw_df": None,
        "cleaned_df": None,
        "quality_report": None,
        "scored_df": None,
        "revenue": None,
        "selected_client_name": None,
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "upload_filename": None,
        # Outreach: persist result across tab switches
        "outreach_result": None,
        "outreach_lead_name": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Clipboard Helper ─────────────────────────────────────────────────────────────
def _copy_button(text: str, button_label: str = "📋 Copy to Clipboard", key: str = "copy"):
    """Render a copy-to-clipboard button using a JS snippet."""
    import streamlit.components.v1 as components
    escaped = text.replace("`", r"\`").replace("$", r"\$")
    components.html(
        f"""
        <button onclick="navigator.clipboard.writeText(`{escaped}`).then(()=>{{this.textContent='✅ Copied!';setTimeout(()=>this.textContent='{button_label}',2000)}})"
                style="background:#1E3A5F;color:white;border:none;padding:7px 16px;border-radius:7px;
                       font-size:0.82rem;cursor:pointer;font-family:Inter,sans-serif;font-weight:500;
                       margin-top:6px;transition:background 0.2s;"
                onmouseover="this.style.background='#2C5F8A'" onmouseout="this.style.background='#1E3A5F'">
          {button_label}
        </button>
        """,
        height=45,
    )

# ── Sidebar ───────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🏢 Realtor Client")

    client_names = get_client_names()
    options = ["— Select a client —"] + client_names + ["➕ Add new client…"]
    sel = st.selectbox("Active Client", options, key="client_selector")

    if sel == "➕ Add new client…":
        with st.form("add_client_form"):
            new_name   = st.text_input("Realtor Name *")
            new_agency = st.text_input("Agency / Brokerage")
            new_email  = st.text_input("Realtor Email")
            new_phone  = st.text_input("Realtor Phone")
            submitted  = st.form_submit_button("Add Client")
            if submitted:
                if not new_name.strip():
                    st.error("Name is required.")
                else:
                    add_client(new_name.strip(), new_email, new_phone, new_agency)
                    st.session_state["selected_client_name"] = new_name.strip()
                    st.success(f"✅ Added: {new_name}")
                    st.rerun()
    elif sel != "— Select a client —":
        st.session_state["selected_client_name"] = sel

    if st.session_state["selected_client_name"]:
        client_obj = get_client_by_name(st.session_state["selected_client_name"])
        if client_obj:
            st.caption(f"📧 {client_obj.get('email','—')}")
            st.caption(f"🏠 {client_obj.get('agency','—')}")
            last = get_last_run(client_obj["id"])
            if last:
                dt = last["run_date"][:10]
                st.caption(f"🕐 Last processed: {dt}")
            else:
                st.caption("🕐 Not yet processed")

    st.divider()
    st.markdown("### ⚙️ Settings")

    deal_value = st.number_input("Avg Deal Value ($)", value=50000, step=5000)
    reactivation_rate = st.slider("Reactivation Rate (%)", 1, 20, 5)
    hot_max   = st.slider("Hot (≤ X days)",  1,  60, 30)
    warm_max  = st.slider("Warm (≤ X days)", 31, 180, 90)
    cold_max  = st.slider("Cold (≤ X days)", 91, 365, 180)

    tiers = {"hot_max_days": hot_max, "warm_max_days": warm_max, "cold_max_days": cold_max}

    st.divider()
    st.markdown("### 🔑 OpenAI (optional)")
    api_key_input = st.text_input(
        "API Key", value=st.session_state["openai_key"],
        type="password", placeholder="sk-…",
        help="Used for AI-generated outreach. Leave blank to use built-in templates."
    )
    if api_key_input != st.session_state["openai_key"]:
        st.session_state["openai_key"] = api_key_input

    model_choice = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"])

# ── Header ────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <h1>🚀 AG Lead Reactivation Engine</h1>
  <p>Turn your dormant leads into closed deals — for real estate agents on retainer.</p>
</div>
""", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📤 Upload & Clean",
    "🎯 Score & Prioritize",
    "✉️ Outreach Generator",
    "👥 Client Dashboard",
    "📊 Monthly Report",
])


# ╔══════════════════════════════════════════════════════════════╗
# ║  TAB 1 — UPLOAD & CLEAN                                     ║
# ╚══════════════════════════════════════════════════════════════╝
with tab1:
    st.markdown('<p class="section-title">Upload Your CRM Export</p>', unsafe_allow_html=True)
    st.markdown("Upload a CSV from any CRM. The engine auto-detects column names and date formats.")

    uploaded = st.file_uploader("Choose a CSV file", type=["csv"], key="csv_uploader")

    if uploaded:
        # Only re-process (and reset scoring) if a NEW file was uploaded
        if uploaded.name != st.session_state.get("upload_filename"):
            try:
                raw = pd.read_csv(uploaded)
                st.session_state["raw_df"] = raw
                st.session_state["upload_filename"] = uploaded.name
                cleaned, report = clean_crm_data(raw)
                st.session_state["cleaned_df"] = cleaned
                st.session_state["quality_report"] = report
                # Reset downstream state only on new upload
                st.session_state["scored_df"] = None
                st.session_state["revenue"] = None
                st.session_state["outreach_result"] = None
                st.session_state["outreach_lead_name"] = None
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")

    if st.session_state.get("cleaned_df") is not None:
        cleaned = st.session_state["cleaned_df"]
        report  = st.session_state["quality_report"]

        # ── Quality Score ──
        score = report["score"]
        score_color = "#16a34a" if score >= 75 else "#ca8a04" if score >= 50 else "#dc2626"
        st.markdown(f"""
        <p class="section-title">Data Quality Score</p>
        <div style="font-size:2rem;font-weight:700;color:{score_color}">{score}<span style="font-size:1rem;color:#64748b">/100</span></div>
        <div class="quality-bar-wrap" style="max-width:400px;">
          <div class="quality-bar-fill" style="width:{score}%;background:{score_color};"></div>
        </div>
        <p style="color:#64748b;font-size:0.85rem">{report['total_rows']:,} leads loaded from <b>{st.session_state['upload_filename']}</b></p>
        """, unsafe_allow_html=True)

        # ── Issues ──
        if report["issues"]:
            st.markdown('<p class="section-title">Issues Found</p>', unsafe_allow_html=True)
            for issue in report["issues"]:
                st.warning(issue)
        else:
            st.markdown('<div class="alert-success">✅ No data quality issues found!</div>', unsafe_allow_html=True)

        # ── Breakdown ──
        st.markdown('<p class="section-title">Field Completeness Breakdown</p>', unsafe_allow_html=True)
        bd = report["breakdown"]
        cols = st.columns(len(bd))
        for i, (metric, val) in enumerate(bd.items()):
            col_color = "#16a34a" if val >= 80 else "#ca8a04" if val >= 60 else "#dc2626"
            cols[i].markdown(f"""
            <div class="metric-card">
              <div class="label">{metric}</div>
              <div class="value" style="color:{col_color}">{val}%</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Preview ──
        st.markdown('<p class="section-title">Cleaned Data Preview</p>', unsafe_allow_html=True)
        flag_cols = [c for c in cleaned.columns if c.startswith("Flag_")]
        has_issues_mask = cleaned[flag_cols].any(axis=1) if flag_cols else pd.Series([False] * len(cleaned))
        n_issues = int(has_issues_mask.sum())

        filter_issues = st.checkbox(f"Show only rows with issues ({n_issues})", value=False)
        display_df = cleaned[has_issues_mask] if filter_issues else cleaned

        # Show core columns cleanly
        core_cols = [c for c in ["Lead_Name","Lead_Type","Email","Phone","Last_Contact_Date","Neighborhood"] if c in display_df.columns]
        st.dataframe(display_df[core_cols + flag_cols].head(200), use_container_width=True, height=320)

        # ── Export ──
        st.markdown('<p class="section-title">Download Cleaned CSV</p>', unsafe_allow_html=True)
        export_df = get_cleaned_export(cleaned)
        st.download_button(
            "⬇️ Download Cleaned CSV",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name=f"cleaned_{st.session_state['upload_filename']}",
            mime="text/csv",
        )

        # ── Proceed button ──
        st.divider()
        if st.button("▶️ Proceed to Scoring →", type="primary"):
            scored, revenue = score_leads(cleaned, tiers=tiers, deal_value=deal_value, reactivation_rate=reactivation_rate)
            st.session_state["scored_df"] = scored
            st.session_state["revenue"]   = revenue

            # Auto-save run if client selected
            client_obj = get_client_by_name(st.session_state["selected_client_name"] or "") if st.session_state["selected_client_name"] else None
            if client_obj:
                record_run(client_obj["id"], revenue, quality_score=report["score"])

            st.success("✅ Scoring complete! Switch to the **Score & Prioritize** tab.")
    else:
        # Empty state
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:#94a3b8;border:2px dashed #cbd5e1;border-radius:12px;margin-top:1rem;">
          <div style="font-size:3rem">📂</div>
          <div style="font-size:1.1rem;font-weight:600;margin-top:0.5rem">No file uploaded yet</div>
          <div style="font-size:0.85rem;margin-top:0.25rem">Upload a CSV to get started. <a href="#" style="color:#2563eb">Download sample CSV</a></div>
        </div>
        """, unsafe_allow_html=True)


# ╔══════════════════════════════════════════════════════════════╗
# ║  TAB 2 — SCORE & PRIORITIZE                                 ║
# ╚══════════════════════════════════════════════════════════════╝
with tab2:
    scored = st.session_state.get("scored_df")
    revenue = st.session_state.get("revenue")

    if scored is None:
        st.markdown("""
        <div class="alert-info">ℹ️ Upload and clean your CRM data in the <b>Upload & Clean</b> tab first, then click "Proceed to Scoring".</div>
        """, unsafe_allow_html=True)
    else:
        # ── Revenue Metrics ──
        st.markdown('<p class="section-title">Opportunity Overview</p>', unsafe_allow_html=True)
        m1, m2, m3, m4, m5 = st.columns(5)
        def metric_card(col, label, value, delta=None, delta_positive=True):
            delta_html = ""
            if delta is not None:
                d_color = "#16a34a" if delta_positive else "#dc2626"
                delta_html = f'<div class="delta" style="color:{d_color}">{delta}</div>'
            col.markdown(f"""
            <div class="metric-card">
              <div class="label">{label}</div>
              <div class="value">{value}</div>
              {delta_html}
            </div>
            """, unsafe_allow_html=True)

        metric_card(m1, "Total Leads", f"{revenue['total_leads']:,}")
        metric_card(m2, "⚫ Dormant (Primary)", f"{revenue['dormant_count']:,}")
        metric_card(m3, "🔴 Hot", f"{revenue['hot_count']:,}")
        metric_card(m4, "Est. Reactivations", f"{revenue['projected_reactivations']:.0f}")
        metric_card(m5, "Projected Revenue", f"${revenue['projected_revenue']:,.0f}")

        st.markdown("")

        # ── Tier filter ──
        st.markdown('<p class="section-title">Lead List</p>', unsafe_allow_html=True)

        col_filter, col_search = st.columns([3, 2])
        with col_filter:
            temp_filter = st.multiselect(
                "Filter by Temperature",
                ["Dormant", "Cold", "Warm", "Hot", "Unknown"],
                default=["Dormant", "Cold", "Warm", "Hot"],
            )
        with col_search:
            search_q = st.text_input("🔍 Search by name / type", placeholder="e.g. John or Buyer")

        filtered = scored[scored["Temperature"].isin(temp_filter)] if temp_filter else scored
        if search_q:
            mask = pd.Series([False] * len(filtered), index=filtered.index)
            for col in ["Lead_Name", "Lead_Type", "Email", "Neighborhood"]:
                if col in filtered.columns:
                    mask |= filtered[col].astype(str).str.contains(search_q, case=False, na=False)
            filtered = filtered[mask]

        # Display columns
        disp_cols = get_display_columns(filtered)
        st.dataframe(
            filtered[disp_cols].rename(columns={"Temp_Badge": "🌡️", "Days_Since_Contact": "Days Idle"}),
            use_container_width=True,
            height=420,
        )
        st.caption(f"Showing {len(filtered):,} of {len(scored):,} leads")

        # ── Buyer / Seller breakdown ──
        buyers, sellers = get_buyer_seller_split(scored)
        bc1, bc2 = st.columns(2)
        with bc1:
            st.markdown('<p class="section-title">🏠 Buyers Summary</p>', unsafe_allow_html=True)
            st.metric("Total Buyers", len(buyers))
            dormant_b = int((buyers["Temperature"] == "Dormant").sum())
            st.metric("Dormant Buyers", dormant_b, delta=f"{dormant_b} to reactivate", delta_color="off")
        with bc2:
            st.markdown('<p class="section-title">🏷️ Sellers Summary</p>', unsafe_allow_html=True)
            st.metric("Total Sellers", len(sellers))
            dormant_s = int((sellers["Temperature"] == "Dormant").sum())
            st.metric("Dormant Sellers", dormant_s, delta=f"{dormant_s} to reactivate", delta_color="off")

        # ── Exports ──
        st.markdown('<p class="section-title">Export</p>', unsafe_allow_html=True)
        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            dormant_df = get_leads_by_temperature(scored, "Dormant")
            st.download_button("⬇️ Dormant Leads CSV", dormant_df.to_csv(index=False).encode(), "dormant_leads.csv", "text/csv")
        with ec2:
            hot_df = get_leads_by_temperature(scored, "Hot")
            st.download_button("⬇️ Hot Leads CSV", hot_df.to_csv(index=False).encode(), "hot_leads.csv", "text/csv")
        with ec3:
            st.download_button("⬇️ Full Scored CSV", scored.to_csv(index=False).encode(), "all_scored_leads.csv", "text/csv")


# ╔══════════════════════════════════════════════════════════════╗
# ║  TAB 3 — OUTREACH GENERATOR                                 ║
# ╚══════════════════════════════════════════════════════════════╝
with tab3:
    scored = st.session_state.get("scored_df")

    if scored is None:
        st.markdown('<div class="alert-info">ℹ️ Score your leads first in the <b>Score & Prioritize</b> tab.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="section-title">Generate Personalized Outreach</p>', unsafe_allow_html=True)

        # Show only cold & dormant by default (primary targets)
        targets = scored[scored["Temperature"].isin(["Dormant", "Cold"])].copy()

        if len(targets) == 0:
            st.info("No cold or dormant leads found. All your leads are Hot or Warm — great!")
        else:
            col_a, col_b = st.columns([2, 1])
            with col_a:
                # Build display list for selector
                if "Lead_Name" in targets.columns:
                    lead_options = targets["Lead_Name"].fillna("Unknown").astype(str).tolist()
                    lead_idxs    = targets.index.tolist()
                else:
                    lead_options = [f"Lead #{i}" for i in range(len(targets))]
                    lead_idxs    = targets.index.tolist()

                # Zip index with badge
                display_options = []
                for idx, name in zip(lead_idxs, lead_options):
                    temp  = targets.loc[idx, "Temperature"] if "Temperature" in targets.columns else "?"
                    badge = TEMPERATURE_COLORS.get(temp, "⬜")
                    days  = targets.loc[idx, "Days_Since_Contact"] if "Days_Since_Contact" in targets.columns else "?"
                    days_str = f"{int(days)}d idle" if not (isinstance(days, float) and np.isnan(days)) else "?"
                    display_options.append(f"{badge} {name} — {temp} ({days_str})")

                selected_display = st.selectbox("Select a lead", display_options)
                sel_pos = display_options.index(selected_display)
                sel_idx = lead_idxs[sel_pos]
                sel_row = targets.loc[sel_idx]

            with col_b:
                temp_sel_filter = st.multiselect(
                    "Show temperatures", ["Dormant", "Cold"], default=["Dormant", "Cold"]
                )
                targets = scored[scored["Temperature"].isin(temp_sel_filter)].copy() if temp_sel_filter else targets

            # Lead info card
            st.markdown('<p class="section-title">Lead Details</p>', unsafe_allow_html=True)
            info_cols = st.columns(4)
            info_fields = [
                ("Lead Name", sel_row.get("Lead_Name", "—")),
                ("Lead Type", sel_row.get("Lead_Type", "—")),
                ("Temperature", sel_row.get("Temperature", "—")),
                ("Priority Score", f"{sel_row.get('Priority_Score','—')} / 10"),
            ]
            for i, (label, val) in enumerate(info_fields):
                info_cols[i].markdown(f"""
                <div class="metric-card">
                  <div class="label">{label}</div>
                  <div class="value" style="font-size:1.1rem">{val}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("")

            gen_btn = st.button("✨ Generate Outreach", type="primary")

            # Clear cached result when a different lead is selected
            if st.session_state.get("outreach_lead_name") != sel_row.get("Lead_Name"):
                st.session_state["outreach_result"] = None

            if gen_btn:
                with st.spinner("Generating personalized outreach…"):
                    result = generate_outreach_for_row(
                        sel_row,
                        api_key=st.session_state["openai_key"] or None,
                        model=model_choice,
                    )
                # Persist across tab switches
                st.session_state["outreach_result"] = result
                st.session_state["outreach_lead_name"] = sel_row.get("Lead_Name")

            # Render persisted result (survives tab switches)
            result = st.session_state.get("outreach_result")
            if result:
                badge = "🤖 AI-generated (OpenAI)" if result["generated_by"] == "openai" else "📝 Template-generated (built-in)"
                st.markdown(f'<div class="alert-info">{badge}</div>', unsafe_allow_html=True)
                st.markdown("")

                col_e, col_v, col_s = st.tabs(["📧 Email", "📞 Voicemail Script", "💬 SMS"])
                with col_e:
                    st.markdown('<p class="section-title">Reactivation Email</p>', unsafe_allow_html=True)
                    st.markdown(f'<div class="outreach-card">{result["email"]}</div>', unsafe_allow_html=True)
                    btn_col, dl_col = st.columns([1, 1])
                    with btn_col:
                        _copy_button(result["email"], "📋 Copy Email", key="copy_email")
                    with dl_col:
                        st.download_button("⬇️ Download .txt", result["email"],
                                           f"email_{sel_row.get('Lead_Name','lead')}.txt", "text/plain",
                                           key="dl_email")

                with col_v:
                    st.markdown('<p class="section-title">Voicemail / Call Script</p>', unsafe_allow_html=True)
                    st.markdown(f'<div class="outreach-card">{result["voicemail"]}</div>', unsafe_allow_html=True)
                    btn_col2, dl_col2 = st.columns([1, 1])
                    with btn_col2:
                        _copy_button(result["voicemail"], "📋 Copy Script", key="copy_voicemail")
                    with dl_col2:
                        st.download_button("⬇️ Download .txt", result["voicemail"],
                                           f"voicemail_{sel_row.get('Lead_Name','lead')}.txt", "text/plain",
                                           key="dl_voicemail")

                with col_s:
                    st.markdown('<p class="section-title">SMS Template</p>', unsafe_allow_html=True)
                    st.markdown(f'<div class="outreach-card">{result["sms"]}</div>', unsafe_allow_html=True)
                    btn_col3, dl_col3 = st.columns([1, 1])
                    with btn_col3:
                        _copy_button(result["sms"], "📋 Copy SMS", key="copy_sms")
                    with dl_col3:
                        st.download_button("⬇️ Download .txt", result["sms"],
                                           f"sms_{sel_row.get('Lead_Name','lead')}.txt", "text/plain",
                                           key="dl_sms")

            # ── Bulk generation hint ──
            st.divider()
            has_key = bool(st.session_state.get("openai_key"))
            key_hint = "" if has_key else " Add your OpenAI key in the sidebar for AI-personalized content."
            st.markdown(f"""
            <div class="alert-info">
            💡 <b>Tip:</b> You have <b>{len(targets):,} {' &amp; '.join(temp_sel_filter) if temp_sel_filter else 'target'} leads</b> ready for outreach.
            Select each one above, then click Generate.{key_hint}
            </div>
            """, unsafe_allow_html=True)


# ╔══════════════════════════════════════════════════════════════╗
# ║  TAB 4 — CLIENT DASHBOARD                                   ║
# ╚══════════════════════════════════════════════════════════════╝
with tab4:
    clients = get_all_clients()

    if not clients:
        st.markdown("""
        <div class="alert-warning">⚠️ No clients yet. Use the sidebar to add your first realtor client.</div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<p class="section-title">All Realtor Clients</p>', unsafe_allow_html=True)

        # Summary cards for each client
        cols_per_row = 3
        for i in range(0, len(clients), cols_per_row):
            row_clients = clients[i:i + cols_per_row]
            cols = st.columns(cols_per_row)
            for j, c in enumerate(row_clients):
                last = get_last_run(c["id"])
                with cols[j]:
                    last_date = last["run_date"][:10] if last else "Never processed"
                    dormant   = last.get("dormant_count", 0) if last else 0
                    total     = last.get("total_leads", 0) if last else 0
                    quality   = last.get("quality_score", "—") if last else "—"
                    is_active = st.session_state["selected_client_name"] == c["name"]
                    border = "border:2px solid #2ECC71;" if is_active else ""
                    st.markdown(f"""
                    <div class="metric-card" style="{border}margin-bottom:1rem">
                      <div style="font-size:1.1rem;font-weight:700;color:#1E3A5F">{"✅ " if is_active else "👤 "}{c['name']}</div>
                      <div style="font-size:0.8rem;color:#64748b;margin:0.2rem 0">{c.get('agency','') or 'No agency'}</div>
                      <hr style="margin:0.5rem 0;border-color:#e2e8f0">
                      <div style="display:flex;justify-content:space-between;margin-top:0.3rem">
                        <span style="font-size:0.8rem">Total Leads</span><b>{total:,}</b>
                      </div>
                      <div style="display:flex;justify-content:space-between">
                        <span style="font-size:0.8rem">⚫ Dormant</span><b>{dormant:,}</b>
                      </div>
                      <div style="display:flex;justify-content:space-between">
                        <span style="font-size:0.8rem">Quality Score</span><b>{quality}/100</b>
                      </div>
                      <div style="font-size:0.75rem;color:#94a3b8;margin-top:0.5rem">Last run: {last_date}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button(f"Switch to {c['name']}", key=f"switch_{c['id']}"):
                        st.session_state["selected_client_name"] = c["name"]
                        st.rerun()

        # ── Selected client detail ──
        active_name = st.session_state.get("selected_client_name")
        if active_name:
            active_obj = get_client_by_name(active_name)
            if active_obj:
                st.markdown(f'<p class="section-title">📋 {active_name} — Detail View</p>', unsafe_allow_html=True)

                runs = get_client_runs(active_obj["id"], limit=10)
                if runs:
                    hist_rows = []
                    for r in runs:
                        hist_rows.append({
                            "Run Date": r["run_date"][:10],
                            "Total Leads": r["total_leads"],
                            "Hot": r["hot_count"],
                            "Warm": r["warm_count"],
                            "Cold": r["cold_count"],
                            "Dormant": r["dormant_count"],
                            "Quality": f"{r['quality_score']}/100",
                        })
                    hist_df = pd.DataFrame(hist_rows)
                    st.dataframe(hist_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No processing history yet for this client. Upload their CSV in the Upload & Clean tab.")

                # Delete button
                st.divider()
                with st.expander("⚠️ Danger Zone"):
                    if st.button(f"🗑️ Delete client '{active_name}'", type="secondary"):
                        delete_client(active_obj["id"])
                        st.session_state["selected_client_name"] = None
                        st.rerun()


# ╔══════════════════════════════════════════════════════════════╗
# ║  TAB 5 — MONTHLY REPORT                                     ║
# ╚══════════════════════════════════════════════════════════════╝
with tab5:
    active_name = st.session_state.get("selected_client_name")

    if not active_name:
        st.markdown('<div class="alert-warning">⚠️ Select a realtor client in the sidebar to view their monthly report.</div>', unsafe_allow_html=True)
    else:
        active_obj = get_client_by_name(active_name)
        if not active_obj:
            st.error("Client not found.")
        else:
            client_id = active_obj["id"]

            st.markdown(f'<p class="section-title">📊 Monthly Retainer Report — {active_name}</p>', unsafe_allow_html=True)

            # Month selector
            months = []
            now = datetime.now()
            for m in range(0, 6):
                from datetime import timedelta
                d = now.replace(day=1) - timedelta(days=m * 28)
                months.append(d.strftime("%Y-%m"))
            months = sorted(set(months), reverse=True)

            selected_month = st.selectbox("Select Month", months, format_func=lambda m: datetime.strptime(m, "%Y-%m").strftime("%B %Y"))

            # Manual tracking inputs
            st.markdown('<p class="section-title">📬 Outreach Tracking (manual)</p>', unsafe_allow_html=True)
            tracking = get_or_create_monthly(client_id, selected_month)

            t1, t2 = st.columns(2)
            with t1:
                outreach_sent = st.number_input(
                    "Outreach Messages Sent", min_value=0,
                    value=int(tracking.get("outreach_sent", 0)), step=1
                )
            with t2:
                responses_received = st.number_input(
                    "Responses Received", min_value=0,
                    value=int(tracking.get("responses_received", 0)), step=1
                )

            notes_val = st.text_area("Notes for this month", value=tracking.get("notes","") or "", height=100)

            if st.button("💾 Save Tracking Data"):
                upsert_monthly_tracking(client_id, selected_month, outreach_sent, responses_received, notes_val)
                st.success("✅ Saved!")

            # Build the summary
            runs = get_client_runs(client_id, limit=6)
            last_run = runs[0] if runs else None
            monthly_data = get_or_create_monthly(client_id, selected_month)
            # refresh after potential save
            monthly_data["outreach_sent"] = outreach_sent
            monthly_data["responses_received"] = responses_received

            summary = build_monthly_summary(active_name, selected_month, last_run, monthly_data, runs)

            # ── Summary metrics ──
            st.markdown('<p class="section-title">This Month at a Glance</p>', unsafe_allow_html=True)
            sm1, sm2, sm3, sm4, sm5 = st.columns(5)
            def sm_card(col, label, val):
                col.markdown(f"""
                <div class="metric-card">
                  <div class="label">{label}</div>
                  <div class="value">{val}</div>
                </div>
                """, unsafe_allow_html=True)

            sm_card(sm1, "Total Leads", summary["total_leads"])
            sm_card(sm2, "⚫ Dormant", summary["dormant_count"])
            sm_card(sm3, "Outreach Sent", summary["outreach_sent"])
            sm_card(sm4, "Responses", summary["responses_received"])
            sm_card(sm5, "Response Rate", f"{summary['response_rate']}%")

            # ── Trend chart ──
            if runs and len(runs) > 1:
                st.markdown('<p class="section-title">Lead Trend (Last Runs)</p>', unsafe_allow_html=True)
                trend_df = build_trend_dataframe(runs)
                if not trend_df.empty:
                    st.line_chart(trend_df.set_index("Date")[["Dormant", "Cold", "Warm", "Hot"]])

            # ── Export ──
            st.markdown('<p class="section-title">Export Report</p>', unsafe_allow_html=True)
            ex1, ex2 = st.columns(2)
            with ex1:
                csv_bytes = export_report_csv(summary)
                st.download_button(
                    "⬇️ Download CSV Report",
                    data=csv_bytes,
                    file_name=f"report_{active_name.replace(' ','_')}_{selected_month}.csv",
                    mime="text/csv",
                )
            with ex2:
                pdf_bytes = export_report_pdf(summary)
                st.download_button(
                    "⬇️ Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"report_{active_name.replace(' ','_')}_{selected_month}.pdf",
                    mime="application/pdf",
                )
            # ── ADMIN: View captured leads ──────────────────────
import os
st.divider()
admin_pw = st.text_input("Admin access:", type="password", key="admin")
if admin_pw == "yourpassword123":  # change this to something only you know
    log_file = "leads_captured.csv"
    if os.path.isfile(log_file):
        import pandas as pd
        leads_df = pd.read_csv(log_file)
        st.success(f"{len(leads_df)} leads captured so far")
        st.dataframe(leads_df)
        st.download_button(
            "Download leads CSV",
            leads_df.to_csv(index=False),
            "captured_leads.csv",
            "text/csv"
        )
    else:
        st.info("No leads captured yet.")
# ── END ADMIN ────────────────────────────────────────
