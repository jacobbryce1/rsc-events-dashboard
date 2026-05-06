import streamlit as st
import pandas as pd
import plotly.express as px
import logging
import time
from datetime import datetime, timezone

from data_collector import EventDataCollector
from incremental_cache import IncrementalCache
from utils import events_to_dataframe, get_status_emoji
from config import RSC_BASE_URL

logging.basicConfig(level=logging.INFO)

RSC_INSTANCE = RSC_BASE_URL.replace("https://", "").replace("http://", "").replace(".my.rubrik.com", "")
VERSION = "1.0.0"
BUILD = "2026.05.04"

st.set_page_config(
    page_title="RSC Cloud Native Workload Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .dashboard-header {
        background: linear-gradient(90deg, #00C4B4 0%, #0078D4 100%);
        padding: 20px 30px; border-radius: 12px;
        color: white; margin-bottom: 20px;
    }
    .instance-banner {
        background: #1A1A2E;
        padding: 10px 20px;
        border-radius: 8px;
        color: #00C4B4;
        font-family: monospace;
        font-size: 0.95em;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .instance-banner .label {
        color: #9E9E9E;
        font-family: sans-serif;
    }
    .instance-banner .url {
        color: #00C4B4;
        font-weight: bold;
    }
    .instance-banner .status-dot {
        width: 10px; height: 10px;
        background: #43A047;
        border-radius: 50%;
        display: inline-block;
    }
    div[data-testid="stMetricValue"] { font-size: 2rem; }
    .stMultiSelect label { font-weight: 600; }
    .disclaimer {
        background: #FFF3E0;
        border-left: 4px solid #FF9800;
        padding: 12px 16px;
        border-radius: 4px;
        margin-top: 10px;
        font-size: 0.85em;
        color: #E65100;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_cache() -> IncrementalCache:
    return IncrementalCache(
        overlap_minutes=5,
        max_age_hours=24.0,
        persist_path=".event_cache.json",
    )


@st.cache_resource
def get_collector() -> EventDataCollector:
    return EventDataCollector()


def load_events(force_full: bool = False) -> pd.DataFrame:
    cache = get_cache()
    collector = get_collector()

    if force_full:
        cache.clear()

    if cache.needs_full_load:
        with st.spinner("⏳ Initial load — scanning last 24 hours (~3 min)..."):
            events = collector.fetch_all_cloud_native_events()
            result = cache.initialize(events)
            st.toast(f"Loaded {result['inserted']} events", icon="✅")
    else:
        with st.spinner("🔄 Updating..."):
            since = cache.incremental_start_time
            new_events = collector.fetch_incremental(since)
            result = cache.merge(new_events)
            if result["inserted"] > 0 or result["updated"] > 0:
                st.toast(
                    f"+{result['inserted']} new, ~{result['updated']} updated",
                    icon="🔄",
                )

    all_events = cache.get_all_events()
    return events_to_dataframe(all_events)


# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        f"### 🛡️ RSC Cloud Native Workload Dashboard\n"
        f"<small style='color:#888'>v{VERSION}</small>",
        unsafe_allow_html=True,
    )
    st.caption(f"Connected to: **{RSC_INSTANCE}**")
    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 Update", use_container_width=True, type="primary"):
            st.rerun()
    with col_b:
        if st.button("🔁 Full Reload", use_container_width=True):
            get_cache().clear()
            st.rerun()

    auto_refresh = st.toggle("Auto-refresh", value=False)
    if auto_refresh:
        refresh_interval = st.select_slider(
            "Interval", options=[15, 30, 60, 120, 300],
            value=60, format_func=lambda x: f"{x}s",
        )
    else:
        refresh_interval = 60

    cache = get_cache()
    cm = cache.metrics
    st.caption(
        f"📦 {cm['event_count']} cached | "
        f"Updated {cm['last_update_age_s']:.0f}s ago | "
        f"Fetches: {cm['incremental_fetches']}"
    )

    st.markdown("---")

    try:
        t0 = time.time()
        df = load_events()
        load_time = time.time() - t0
        st.success(f"✅ {len(df)} events ({load_time:.1f}s)")
    except Exception as e:
        st.error(f"❌ Failed: {e}")
        st.stop()

    if df.empty:
        st.warning("No events found in the last 24 hours.")
        st.stop()

    st.markdown("---")
    st.markdown("### 🔍 Filters")

    available_statuses = sorted(df["status_category"].unique().tolist())
    selected_statuses = st.multiselect(
        "📊 Status",
        options=available_statuses,
        default=available_statuses,
        help="Filter events by status category",
    )

    available_workloads = sorted(df["object_type_display"].unique().tolist())
    selected_workloads = st.multiselect(
        "☁️ Workload Type",
        options=available_workloads,
        default=available_workloads,
        help="Filter by cloud native workload type",
    )

    available_job_types = sorted(df["job_type"].unique().tolist())
    selected_job_types = st.multiselect(
        "🔨 Job Type",
        options=available_job_types,
        default=available_job_types,
        help="Filter by job/activity type",
    )

    available_clusters = sorted(df["cluster_name"].unique().tolist())
    if len(available_clusters) > 1:
        selected_clusters = st.multiselect(
            "🏢 Cluster",
            options=available_clusters,
            default=available_clusters,
        )
    else:
        selected_clusters = available_clusters

    search_term = st.text_input(
        "🔎 Search by Name or ID", "",
        help="Case-insensitive search",
    )

    st.markdown("---")
    st.markdown("**Quick Filters:**")
    qf1, qf2, qf3 = st.columns(3)
    with qf1:
        if st.button("🔴 Failed", use_container_width=True):
            st.session_state["quick_filter"] = "Failed"
            st.rerun()
    with qf2:
        if st.button("🔵 Active", use_container_width=True):
            st.session_state["quick_filter"] = "Active"
            st.rerun()
    with qf3:
        if st.button("📋 All", use_container_width=True):
            st.session_state["quick_filter"] = None
            st.rerun()

    st.markdown("---")
    st.markdown(
        "**Sort Priority:**\n"
        "1. 🔵 In Progress\n2. 🟡 Queued\n3. 🔴 Failed\n"
        "4. 🟠 Partial\n5. ⚪ Canceled\n6. 🟢 Completed"
    )


# ─────────────────────────────────────────────────────────────
# Apply Filters
# ─────────────────────────────────────────────────────────────

filtered_df = df.copy()

quick_filter = st.session_state.get("quick_filter")
if quick_filter == "Failed":
    filtered_df = filtered_df[filtered_df["status_category"].isin(["Failed", "Partial"])]
elif quick_filter == "Active":
    filtered_df = filtered_df[filtered_df["status_category"].isin(["In Progress", "Queued"])]

if selected_statuses and quick_filter is None:
    filtered_df = filtered_df[filtered_df["status_category"].isin(selected_statuses)]
if selected_workloads:
    filtered_df = filtered_df[filtered_df["object_type_display"].isin(selected_workloads)]
if selected_job_types:
    filtered_df = filtered_df[filtered_df["job_type"].isin(selected_job_types)]
if selected_clusters:
    filtered_df = filtered_df[filtered_df["cluster_name"].isin(selected_clusters)]
if search_term:
    mask = (
        filtered_df["object_name"].str.contains(search_term, case=False, na=False)
        | filtered_df["object_id"].str.contains(search_term, case=False, na=False)
    )
    filtered_df = filtered_df[mask]

filtered_df = filtered_df.sort_values(
    by=["status_sort", "start_timestamp"], ascending=[True, False],
)


# ─────────────────────────────────────────────────────────────
# Instance Banner + Header
# ─────────────────────────────────────────────────────────────

st.markdown(f"""
<div class="instance-banner">
    <span class="status-dot"></span>
    <span class="label">RSC Instance:</span>
    <span class="url">{RSC_INSTANCE}</span>
    <span class="label" style="margin-left: auto;">
        {RSC_BASE_URL}
    </span>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="dashboard-header">
    <h1 style="margin:0;">🛡️ RSC Cloud Native Workload Dashboard</h1>
    <p style="margin:5px 0 0 0; font-size:1.1em; opacity:0.9;">
        Job events across all cloud native workloads — Rolling 24-hour view
    </p>
</div>
""", unsafe_allow_html=True)

# Active filter indicator
active_filters = []
if quick_filter:
    active_filters.append(f"Quick: {quick_filter}")
if search_term:
    active_filters.append(f"Search: '{search_term}'")
if len(selected_statuses) < len(available_statuses):
    active_filters.append(f"Status: {len(selected_statuses)}/{len(available_statuses)}")
if len(selected_workloads) < len(available_workloads):
    active_filters.append(f"Workload: {len(selected_workloads)}/{len(available_workloads)}")
if len(selected_job_types) < len(available_job_types):
    active_filters.append(f"Job: {len(selected_job_types)}/{len(available_job_types)}")

if active_filters:
    st.info(f"🔍 Active filters: {' | '.join(active_filters)} — Showing {len(filtered_df)}/{len(df)} events")


# ─────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────

counts = filtered_df["status_category"].value_counts()
kpi_cols = st.columns(7)
kpi_items = [
    ("📋 Total", len(filtered_df)),
    ("🔵 In Progress", counts.get("In Progress", 0)),
    ("🟡 Queued", counts.get("Queued", 0)),
    ("🔴 Failed", counts.get("Failed", 0)),
    ("🟠 Partial", counts.get("Partial", 0)),
    ("⚪ Canceled", counts.get("Canceled", 0)),
    ("🟢 Completed", counts.get("Completed", 0)),
]
for col, (label, val) in zip(kpi_cols, kpi_items):
    with col:
        st.metric(label, val)

unknown = counts.get("Unknown", 0)
if unknown > 0:
    st.caption(f"⚫ {unknown} unmapped status")

st.markdown("---")


# ─────────────────────────────────────────────────────────────
# Charts
# ─────────────────────────────────────────────────────────────

color_map = {
    "In Progress": "#1E88E5", "Queued": "#FFA726", "Failed": "#E53935",
    "Partial": "#FF7043", "Canceled": "#9E9E9E", "Completed": "#43A047",
    "Unknown": "#757575",
}

c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("Status")
    sc = filtered_df["status_category"].value_counts().reset_index()
    sc.columns = ["Status", "Count"]
    fig = px.pie(sc, values="Count", names="Status", color="Status",
                 color_discrete_map=color_map, hole=0.4)
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("By Workload")
    wc = filtered_df["object_type_display"].value_counts().head(12).reset_index()
    wc.columns = ["Workload", "Count"]
    fig = px.bar(wc, x="Count", y="Workload", orientation="h",
                 color="Count", color_continuous_scale="Viridis")
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300,
                      showlegend=False, yaxis=dict(autorange="reversed"),
                      coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

with c3:
    st.subheader("By Job Type")
    jc = filtered_df["job_type"].value_counts().head(12).reset_index()
    jc.columns = ["Job Type", "Count"]
    fig = px.bar(jc, x="Count", y="Job Type", orientation="h",
                 color="Count", color_continuous_scale="Sunset")
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300,
                      showlegend=False, yaxis=dict(autorange="reversed"),
                      coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# Timeline
# ─────────────────────────────────────────────────────────────

st.subheader("📈 Timeline")
tdf = filtered_df.copy()
tdf["start_dt"] = pd.to_datetime(tdf["start_time_formatted"],
                                  format="%Y-%m-%d %H:%M:%S UTC", errors="coerce")
tdf = tdf.dropna(subset=["start_dt"])
if not tdf.empty:
    tdf["hour"] = tdf["start_dt"].dt.floor("h")
    hourly = tdf.groupby(["hour", "status_category"]).size().reset_index(name="count")
    fig = px.bar(hourly, x="hour", y="count", color="status_category",
                 color_discrete_map=color_map, barmode="stack",
                 labels={"hour": "Time", "count": "Jobs", "status_category": "Status"})
    fig.update_layout(margin=dict(t=20, b=40, l=40, r=20), height=250,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                  xanchor="right", x=1),
                      xaxis_title="", yaxis_title="Jobs")
    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# Failed Jobs Detail
# ─────────────────────────────────────────────────────────────

failed_count = counts.get("Failed", 0) + counts.get("Partial", 0)
if failed_count > 0:
    with st.expander(f"🔴 Failed / Partial Jobs ({failed_count})", expanded=True):
        fdf = filtered_df[filtered_df["status_category"].isin(["Failed", "Partial"])]
        st.dataframe(
            fdf[["object_name", "object_type_display", "job_type",
                 "start_time_formatted", "end_time_formatted",
                 "elapsed_formatted", "raw_status", "last_message"]
            ].rename(columns={
                "object_name": "Object",
                "object_type_display": "Type",
                "job_type": "Job",
                "start_time_formatted": "Start Time",
                "end_time_formatted": "End Time",
                "elapsed_formatted": "Duration",
                "raw_status": "Status",
                "last_message": "Error",
            }),
            use_container_width=True, hide_index=True,
        )


# ─────────────────────────────────────────────────────────────
# Main Events Table
# ─────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader(f"📋 All Events ({len(filtered_df)})")

display_df = filtered_df[[
    "status_category", "object_name", "object_id", "object_type_display",
    "job_type", "start_time_formatted", "end_time_formatted",
    "elapsed_formatted", "data_transferred_formatted",
    "logical_size_formatted", "progress",
    "throughput_formatted", "cluster_name",
]].copy()

display_df["status_category"] = display_df["status_category"].apply(
    lambda s: f"{get_status_emoji(s)} {s}"
)
display_df["progress"] = display_df["progress"].apply(
    lambda p: f"{p}%" if p is not None and str(p) != "N/A" else "N/A"
)
display_df = display_df.rename(columns={
    "status_category": "Status",
    "object_name": "Object Name",
    "object_id": "Object ID",
    "object_type_display": "Workload Type",
    "job_type": "Job Type",
    "start_time_formatted": "Start Time (UTC)",
    "end_time_formatted": "End Time (UTC)",
    "elapsed_formatted": "Elapsed",
    "data_transferred_formatted": "Data Transferred",
    "logical_size_formatted": "Logical Size",
    "progress": "Progress",
    "throughput_formatted": "Throughput",
    "cluster_name": "Cluster",
})

st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)


# ─────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────

st.markdown("---")
ec1, ec2, _ = st.columns([1, 1, 3])
with ec1:
    st.download_button(
        "📥 CSV", display_df.to_csv(index=False).encode("utf-8"),
        f"rsc_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "text/csv", use_container_width=True,
    )
with ec2:
    st.download_button(
        "📥 JSON", filtered_df.to_json(orient="records", indent=2).encode("utf-8"),
        f"rsc_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        "application/json", use_container_width=True,
    )


# ─────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────

st.markdown("---")
st.caption(
    f"🛡️ RSC Cloud Native Workload Dashboard v{VERSION} (build {BUILD}) | "
    f"Instance: {RSC_INSTANCE} | "
    f"Rolling 24h | "
    f"Cache: {cm['event_count']} events | "
    f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
)

# Disclaimer
st.markdown("""
<div class="disclaimer">
    ⚠️ <strong>Disclaimer:</strong> This is not a Rubrik built or maintained solution
    and carries no support or warranties.
</div>
""", unsafe_allow_html=True)

# Built by
st.markdown("---")
_, center_col, _ = st.columns([2, 1, 2])
with center_col:
    st.image("assets/jacob_bryce.png", width=150)


# ─────────────────────────────────────────────────────────────
# Auto-refresh
# ─────────────────────────────────────────────────────────────

if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
