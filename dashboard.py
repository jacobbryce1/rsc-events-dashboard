import streamlit as st
import pandas as pd
import plotly.express as px
import logging
import time
from datetime import datetime, timezone

from data_collector import EventDataCollector
from utils import events_to_dataframe, get_status_emoji

logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="RSC Cloud Native Events Dashboard",
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
    div[data-testid="stMetricValue"] { font-size: 2rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_events() -> pd.DataFrame:
    """Load events with parallel collection."""
    collector = EventDataCollector(max_workers=8, page_size=200)
    events = collector.fetch_all_cloud_native_events()
    return events_to_dataframe(events)


with st.sidebar:
    st.markdown("### 🛡️ RSC Dashboard")
    st.markdown("---")

    if st.button("🔄 Refresh Data", use_container_width=True, type="primary"):
        load_events.clear()
        st.rerun()

    st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    st.markdown("---")

    try:
        with st.spinner("⏳ Fetching events from RSC (parallel)..."):
            t0 = time.time()
            df = load_events()
            load_time = time.time() - t0
        st.success(f"Loaded {len(df)} events in {load_time:.1f}s")
    except Exception as e:
        st.error(f"❌ Failed to load events: {e}")
        st.stop()

    if df.empty:
        st.warning("No events found in the last 24 hours.")
        st.stop()

    available_workloads = sorted(df["object_type_display"].unique().tolist())
    selected_workloads = st.multiselect(
        "☁️ Workload Type", options=available_workloads, default=available_workloads,
    )

    available_statuses = sorted(df["status_category"].unique().tolist())
    selected_statuses = st.multiselect(
        "📊 Status", options=available_statuses, default=available_statuses,
    )

    available_job_types = sorted(df["job_type"].unique().tolist())
    selected_job_types = st.multiselect(
        "🔨 Job Type", options=available_job_types, default=available_job_types,
    )

    available_clusters = sorted(df["cluster_name"].unique().tolist())
    if len(available_clusters) > 1:
        selected_clusters = st.multiselect(
            "🏢 Cluster", options=available_clusters, default=available_clusters,
        )
    else:
        selected_clusters = available_clusters

    search_term = st.text_input("🔍 Search (Object Name / ID)", "")

    st.markdown("---")
    st.markdown(
        "**Sort Priority:**\n"
        "1. 🔵 In Progress\n2. 🟡 Queued\n3. 🔴 Failed\n"
        "4. 🟠 Partial\n5. ⚪ Canceled\n6. 🟢 Completed"
    )

# ── Apply Filters ──
filtered_df = df.copy()
if selected_workloads:
    filtered_df = filtered_df[filtered_df["object_type_display"].isin(selected_workloads)]
if selected_statuses:
    filtered_df = filtered_df[filtered_df["status_category"].isin(selected_statuses)]
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

# ── Header ──
st.markdown("""
<div class="dashboard-header">
    <h1 style="margin:0;">🛡️ RSC Cloud Native Events Dashboard</h1>
    <p style="margin:5px 0 0 0; font-size:1.1em; opacity:0.9;">
        Job events across all cloud native workloads — Last 24 Hours
    </p>
</div>
""", unsafe_allow_html=True)

# ── KPIs ──
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
    st.caption(f"⚫ {unknown} events with unmapped status")

st.markdown("---")

# ── Charts ──
color_map = {
    "In Progress": "#1E88E5", "Queued": "#FFA726", "Failed": "#E53935",
    "Partial": "#FF7043", "Canceled": "#9E9E9E", "Completed": "#43A047",
    "Unknown": "#757575",
}

c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("Status Distribution")
    sc = filtered_df["status_category"].value_counts().reset_index()
    sc.columns = ["Status", "Count"]
    fig = px.pie(sc, values="Count", names="Status", color="Status",
                 color_discrete_map=color_map, hole=0.4)
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("By Workload Type")
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

# ── Timeline ──
st.subheader("📈 Job Timeline (Last 24 Hours)")
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
                      xaxis_title="", yaxis_title="Job Count")
    st.plotly_chart(fig, use_container_width=True)

# ── Failed Jobs ──
failed_count = counts.get("Failed", 0)
if failed_count > 0:
    with st.expander(f"🔴 Failed Jobs ({failed_count})", expanded=True):
        fdf = filtered_df[filtered_df["status_category"] == "Failed"]
        st.dataframe(
            fdf[["object_name", "object_type_display", "job_type",
                 "start_time_formatted", "elapsed_formatted", "last_message"]
            ].rename(columns={
                "object_name": "Object", "object_type_display": "Type",
                "job_type": "Job", "start_time_formatted": "Start",
                "elapsed_formatted": "Duration", "last_message": "Error",
            }),
            use_container_width=True, hide_index=True,
        )

# ── Main Table ──
st.markdown("---")
st.subheader(f"📋 All Job Events ({len(filtered_df)} records)")

display_df = filtered_df[[
    "status_category", "object_name", "object_id", "object_type_display",
    "job_type", "start_time_formatted", "elapsed_formatted",
    "data_transferred_formatted", "logical_size_formatted", "progress",
    "throughput_formatted", "cluster_name",
]].copy()

display_df["status_category"] = display_df["status_category"].apply(
    lambda s: f"{get_status_emoji(s)} {s}"
)
display_df["progress"] = display_df["progress"].apply(
    lambda p: f"{p}%" if p is not None and str(p) != "N/A" else "N/A"
)
display_df = display_df.rename(columns={
    "status_category": "Status", "object_name": "Object Name",
    "object_id": "Object ID", "object_type_display": "Workload Type",
    "job_type": "Job Type", "start_time_formatted": "Start Time (UTC)",
    "elapsed_formatted": "Elapsed", "data_transferred_formatted": "Data Transferred",
    "logical_size_formatted": "Logical Size", "progress": "Progress",
    "throughput_formatted": "Throughput", "cluster_name": "Cluster",
})

st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)

# ── Export ──
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

st.markdown("---")
st.caption(
    f"🛡️ RSC Cloud Native Events Dashboard | Last 24h | "
    f"Auto-refresh: 5 min | "
    f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
)
