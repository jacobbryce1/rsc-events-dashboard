"""
Test 5: Full end-to-end test.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from data_collector import EventDataCollector
from utils import events_to_dataframe
from tabulate import tabulate


def test_full_pipeline():
    print("\n🎯 Running full end-to-end pipeline...\n")

    collector = EventDataCollector()
    events = collector.fetch_all_cloud_native_events()

    if not events:
        print("⚠️  No events found. Dashboard would show empty state.")
        return

    df = events_to_dataframe(events)
    print(f"✅ DataFrame created: {len(df)} rows × {len(df.columns)} columns\n")

    display_cols = [
        "status_category", "object_name", "object_id", "object_type_display",
        "job_type", "start_time_formatted", "elapsed_formatted",
        "data_transferred_formatted", "logical_size_formatted",
    ]
    col_names = [
        "Status", "Object Name", "Object ID", "Workload Type",
        "Job Type", "Start Time", "Elapsed", "Data Xfer", "Logical Size",
    ]

    for status in ["In Progress", "Queued", "Failed", "Partial", "Canceled", "Completed"]:
        subset = df[df["status_category"] == status].head(5)
        if subset.empty:
            print(f"\n{'='*80}")
            print(f"  {status}: (no events)")
            continue

        total_in_status = len(df[df["status_category"] == status])
        print(f"\n{'='*80}")
        print(f"  {status}: {total_in_status} total (showing first {len(subset)})")
        print(f"{'='*80}")

        display_data = subset[display_cols].copy()
        display_data["object_name"] = display_data["object_name"].str[:30]
        display_data["object_id"] = display_data["object_id"].str[:20]

        print(tabulate(
            display_data.values, headers=col_names,
            tablefmt="simple_grid", maxcolwidths=30,
        ))

    print(f"\n{'='*80}")
    print("  SUMMARY")
    print(f"{'='*80}")
    print(f"  Total Events:      {len(df)}")
    print(f"  Workload Types:    {df['object_type_display'].nunique()}")
    print(f"  Job Types:         {df['job_type'].nunique()}")
    print(f"  Time Range:        {df['start_time_formatted'].min()} → {df['start_time_formatted'].max()}")
    print(f"  Status Breakdown:")
    for status, count in df["status_category"].value_counts().items():
        print(f"    {status:<15} {count}")


def test_dashboard_data_shapes():
    print("\n🎯 Validating dashboard data shapes...")

    collector = EventDataCollector()
    events = collector.fetch_all_cloud_native_events()
    df = events_to_dataframe(events)

    if df.empty:
        print("   ⚠️  Empty DataFrame")
        return

    workloads = sorted(df["object_type_display"].unique().tolist())
    statuses = sorted(df["status_category"].unique().tolist())
    job_types = sorted(df["job_type"].unique().tolist())

    print(f"   ✅ Workload filter options ({len(workloads)}):")
    for w in workloads:
        print(f"      • {w}")

    print(f"\n   ✅ Status filter options ({len(statuses)}):")
    for s in statuses:
        print(f"      • {s}")

    print(f"\n   ✅ Job type filter options ({len(job_types)}):")
    for j in job_types[:15]:
        print(f"      • {j}")
    if len(job_types) > 15:
        print(f"      ... and {len(job_types) - 15} more")

    critical_cols = ["status_category", "object_name", "job_type", "start_time_formatted"]
    for col in critical_cols:
        null_count = df[col].isna().sum() + (df[col] == "").sum()
        icon = "✅" if null_count == 0 else "⚠️"
        print(f"\n   {icon} Column '{col}': {null_count} null/empty values")


if __name__ == "__main__":
    test_full_pipeline()
    test_dashboard_data_shapes()

    print(f"\n{'='*60}")
    print("✅ End-to-end tests complete.")
    print("   If the data above looks correct, run: streamlit run dashboard.py")
