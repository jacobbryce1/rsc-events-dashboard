import pandas as pd
from typing import List, Dict, Any


def events_to_dataframe(events: List[Dict[str, Any]]) -> pd.DataFrame:
    if not events:
        return pd.DataFrame()

    df = pd.DataFrame(events)

    display_columns = [
        "status_category", "object_name", "object_id", "object_type_display",
        "job_type", "start_time_formatted", "end_time_formatted",
        "elapsed_formatted", "data_transferred_formatted",
        "logical_size_formatted", "progress", "throughput_formatted",
        "cluster_name", "location", "last_message",
        "raw_status", "raw_job_type", "object_type", "status_sort",
        "start_timestamp", "elapsed_seconds", "data_transferred_bytes",
        "logical_size_bytes", "id", "activity_series_id", "severity",
    ]

    for col in display_columns:
        if col not in df.columns:
            df[col] = "N/A"

    return df[display_columns]


def get_status_color(status_category: str) -> str:
    return {
        "In Progress": "#1E88E5",
        "Queued": "#FFA726",
        "Failed": "#E53935",
        "Partial": "#FF7043",
        "Canceled": "#9E9E9E",
        "Completed": "#43A047",
        "Unknown": "#757575",
    }.get(status_category, "#757575")


def get_status_emoji(status_category: str) -> str:
    return {
        "In Progress": "🔵",
        "Queued": "🟡",
        "Failed": "🔴",
        "Partial": "🟠",
        "Canceled": "⚪",
        "Completed": "🟢",
        "Unknown": "⚫",
    }.get(status_category, "⚫")
