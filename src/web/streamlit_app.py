import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import glob
from datetime import datetime
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="AutoApply Intelligence Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Theme / Custom CSS ---
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #161b22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .report-card {
        background-color: #0d1117;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #30363d;
        margin-bottom: 20px;
    }
    h1, h2, h3 {
        color: #58a6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Data Loading Utilities ---

def load_latest_run():
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        return None
    
    run_logs = glob.glob(os.path.join(logs_dir, "run-*.json"))
    if not run_logs:
        return None
    
    latest_log = max(run_logs, key=os.path.getctime)
    try:
        with open(latest_log, 'r') as f:
            return json.load(f)
    except Exception:
        return None

def load_scraper_metrics():
    logs_dir = "logs"
    today_str = datetime.now().strftime('%Y%m%d')
    metrics_file = os.path.join(logs_dir, f"scraper_metrics_{today_str}.json")
    
    if os.path.exists(metrics_file):
        try:
            with open(metrics_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def load_latest_report():
    reports_dir = os.path.join("logs", "reports")
    if not os.path.exists(reports_dir):
        return None
    
    reports = glob.glob(os.path.join(reports_dir, "report-*.md"))
    if not reports:
        return None
    
    latest_report = max(reports, key=os.path.getctime)
    try:
        with open(latest_report, 'r', encoding='utf-8') as f:
            return f.read(), os.path.basename(latest_report)
    except Exception:
        return None, None

# --- Dashboard Layout ---

st.sidebar.title("🚀 AutoApply AI")
st.sidebar.subheader("Multi-Agent Pipeline")

# System Status
run_data = load_latest_run()
if run_data:
    st.sidebar.success("System Operational")
    st.sidebar.caption(f"Last Run: {run_data.get('ended_at', 'N/A')[:19]}")
else:
    st.sidebar.warning("System Idle")

# Sidebar Metrics
if run_data:
    counts = run_data.get("agent_counts", {})
    st.sidebar.divider()
    st.sidebar.metric("CVs Generated", counts.get("cvs_generated", 0))
    st.sidebar.metric("Apps Submitted", counts.get("applications_submitted", 0))

st.sidebar.divider()
if st.sidebar.button("Refresh Data"):
    st.rerun()

# --- Main Page ---

st.title("Pipeline Intelligence Dashboard")
st.markdown("---")

# Main Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Performance", "🕵️ Scrapers", "📄 Latest Report", "🛠️ System Health"])

with tab1:
    if run_data:
        counts = run_data.get("agent_counts", {})
        
        # Top Level Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Jobs Discovered", counts.get("jobs_discovered", 0))
        with col2:
            st.metric("Qualified (CP1)", counts.get("cp1_gate", 0))
        with col3:
            st.metric("Tailored (CP2)", counts.get("cvs_generated", 0))
        with col4:
            st.metric("Execution", counts.get("applications_submitted", 0))
            
        st.markdown("### Pipeline Funnel")
        
        # Funnel Chart
        funnel_data = dict(
            number=[
                counts.get("jobs_discovered", 0),
                counts.get("cp1_gate", 0),
                counts.get("cvs_generated", 0),
                counts.get("applications_submitted", 0)
            ],
            stage=["Discovered", "Qualified", "Tailored", "Applied"]
        )
        fig = px.funnel(funnel_data, x='number', y='stage', color_discrete_sequence=['#58a6ff'])
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="#c9d1d9")
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("No run data available. Start the orchestrator to see metrics.")

with tab2:
    st.subheader("Web Scraper Health")
    scraper_data = load_scraper_metrics()
    
    if scraper_data:
        # Convert to DataFrame
        df_list = []
        for portal, metrics in scraper_data.items():
            metrics['Portal'] = portal
            df_list.append(metrics)
        
        df = pd.DataFrame(df_list)
        
        # Success Rate Chart
        fig = px.bar(df, x='Portal', y='success_rate', color='success_rate',
                     title="Scraper Success Rates",
                     color_continuous_scale='Viridis',
                     labels={'success_rate': 'Success %'})
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="#c9d1d9")
        st.plotly_chart(fig, use_container_width=True)
        
        # Metrics Table
        st.dataframe(df[['Portal', 'requests_sent', 'successful_scrapes', 'failed_scrapes', 'jobs_discovered', 'blocked_ips']], 
                     use_container_width=True)
    else:
        st.warning("No scraper metrics found for today.")

with tab3:
    report_content, report_name = load_latest_report()
    if report_content:
        st.subheader(f"Latest Report: {report_name}")
        st.markdown(f'<div class="report-card">{report_content}</div>', unsafe_allow_html=True)
        
        # Download button
        st.download_button(
            label="Download Report (Markdown)",
            data=report_content,
            file_name=report_name,
            mime="text/markdown"
        )
    else:
        st.info("No reports generated yet.")

with tab4:
    st.subheader("System Events & Errors")
    if run_data:
        errors = run_data.get("errors", [])
        if errors:
            err_df = pd.DataFrame(errors)
            st.table(err_df)
        else:
            st.success("No critical errors reported in the last run.")
            
        st.divider()
        st.subheader("Orchestrator Config")
        # Show key env vars (masked)
        st.json({
            "DRY_RUN": os.getenv("DRY_RUN"),
            "USE_MOCK_JOBS": os.getenv("USE_MOCK_JOBS"),
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER"),
            "ENABLE_NAUKRI": os.getenv("ENABLE_NAUKRI_SCRAPING"),
            "ENABLE_CUTSHORT": os.getenv("ENABLE_CUTSHORT_SCRAPING"),
        })
    else:
        st.info("System health metrics will appear after the first run.")

# --- Footer ---
st.markdown("---")
st.caption("AutoApply Multi-Agent System | Phase 10 Observability Dashboard")
