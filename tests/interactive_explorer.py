# interactive_explorer.py
"""
Interactive tool for exploring RSC data.
Useful for debugging queries and understanding your environment.

Usage: python interactive_explorer.py
"""
import sys
import os
import json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()

from rsc_client import RSCClient
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich import print as rprint

console = Console()
client = RSCClient()


def explore_recent_events(hours=24, limit=20):
    """Fetch and display recent events."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)

    query = """
    query Explore($first: Int, $filters: ActivitySeriesFilter) {
        activitySeriesConnection(first: $first, filters: $filters, sortBy: START_TIME, sortOrder: DESC) {
            nodes {
                id
                fid
                activitySeriesId
                lastActivityType
                lastActivityStatus
                objectId
                objectName
                objectType
                startTime
                lastUpdated
                progress
                dataTransferred
                logicalSize
                effectiveThroughput
                location
                severity
                cluster { id name }
            }
            pageInfo { hasNextPage endCursor }
        }
    }
    """

    variables = {
        "first": limit,
        "filters": {
            "startTimeGt": start.isoformat(),
            "startTimeLt": now.isoformat(),
        },
    }

    result = client.execute_query(query, variables)
    nodes = result.get("activitySeriesConnection", {}).get("nodes", [])

    table = Table(title=f"Recent Events (last {hours}h, limit {limit})")
    table.add_column("Status", style="bold")
    table.add_column("Object Name")
    table.add_column("Type")
    table.add_column("Job")
    table.add_column("Start Time")
    table.add_column("Data Xfer")
    table.add_column("Size")

    status_colors = {
        "SUCCESS": "green", "COMPLETED": "green", "SUCCEEDED": "green",
        "RUNNING": "blue", "IN_PROGRESS": "blue", "ACTIVE": "blue",
        "QUEUED": "yellow", "PENDING": "yellow",
        "FAILED": "red", "CANCELED": "red",
    }

    for node in nodes:
        status = node.get("lastActivityStatus", "?")
        color = status_colors.get(status, "white")

        table.add_row(
            f"[{color}]{status}[/{color}]",
            (node.get("objectName") or "N/A")[:40],
            (node.get("objectType") or "N/A")[:25],
            (node.get("lastActivityType") or "N/A")[:25],
            (node.get("startTime") or "N/A")[:19],
            str(node.get("dataTransferred") or "—"),
            str(node.get("logicalSize") or "—"),
        )

    console.print(table)
    return nodes


def explore_workload_type(workload_type, hours=24):
    """Deep-dive into a specific workload type."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)

    query = """
    query WorkloadExplore($first: Int, $filters: ActivitySeriesFilter) {
        activitySeriesConnection(first: $first, filters: $filters, sortBy: START_TIME, sortOrder: DESC) {
            nodes {
                lastActivityType
                lastActivityStatus
                objectName
                objectId
                startTime
                lastUpdated
                dataTransferred
                logicalSize
                progress
            }
            pageInfo { hasNextPage }
        }
    }
    """

    variables = {
        "first": 50,
        "filters": {
            "objectType": [workload_type],
            "startTimeGt": start.isoformat(),
            "startTimeLt": now.isoformat(),
        },
    }

    result = client.execute_query(query, variables)
    nodes = result.get("activitySeriesConnection", {}).get("nodes", [])

    console.print(f"\n[bold]{workload_type}[/bold]: {len(nodes)} events\n")

    for i, node in enumerate(nodes[:10]):
        console.print(Panel(
            json.dumps(node, indent=2, default=str),
            title=f"Event {i+1}: {node.get('objectName', 'N/A')}",
            subtitle=f"{node.get('lastActivityStatus')} — {node.get('lastActivityType')}",
        ))


def dump_raw_event(event_index=0, hours=24):
    """Dump a single raw event for debugging field availability."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)

    query = """
    query RawDump($first: Int, $filters: ActivitySeriesFilter) {
        activitySeriesConnection(first: $first, filters: $filters, sortBy: START_TIME, sortOrder: DESC) {
            nodes {
                id fid activitySeriesId
                lastActivityType lastActivityStatus
                objectId objectName objectType
                startTime lastUpdated
                progress
                dataTransferred logicalSize effectiveThroughput
                location severity
                cluster { id name }
                activityConnection(first: 3, sortOrder: DESC) {
                    nodes {
                        id message status time severity
                    }
                }
            }
        }
    }
    """

    variables = {
        "first": event_index + 1,
        "filters": {
            "startTimeGt": start.isoformat(),
            "startTimeLt": now.isoformat(),
        },
    }

    result = client.execute_query(query, variables)
    nodes = result.get("activitySeriesConnection", {}).get("nodes", [])

    if event_index < len(nodes):
        node = nodes[event_index]
        console.print(Panel(
            json.dumps(node, indent=2, default=str),
            title=f"[bold]Raw Event Dump #{event_index}[/bold]",
            subtitle=f"{node.get('objectName')} — {node.get('objectType')}",
        ))

        # Field analysis
        console.print("\n[bold]Field Analysis:[/bold]")
        for key, value in node.items():
            if key == "activityConnection":
                continue
            populated = value is not None and value != "" and value != {}
            icon = "✅" if populated else "⬜"
            console.print(f"  {icon} {key}: {repr(value)}")
    else:
        console.print(f"[red]No event at index {event_index}[/red]")


def interactive_menu():
    """Interactive exploration menu."""
    console.print(Panel(
        "[bold]RSC Data Explorer[/bold]\n"
        "Interactively explore your RSC events data",
        style="blue",
    ))

    while True:
        console.print("\n[bold]Options:[/bold]")
        console.print("  1. View recent events (all types)")
        console.print("  2. Explore specific workload type")
        console.print("  3. Dump raw event JSON")
        console.print("  4. Count events by workload type")
        console.print("  5. Count events by status")
        console.print("  6. Test custom time window")
        console.print("  q. Quit")

        choice = Prompt.ask("\nChoice", choices=["1", "2", "3", "4", "5", "6", "q"])

        if choice == "q":
            break
        elif choice == "1":
            hours = IntPrompt.ask("Hours to look back", default=24)
            limit = IntPrompt.ask("Max events to show", default=20)
            explore_recent_events(hours=hours, limit=limit)
        elif choice == "2":
            from config import CLOUD_NATIVE_WORKLOAD_TYPES, WORKLOAD_DISPLAY_NAMES
            console.print("\n[bold]Available workload types:[/bold]")
            for i, wt in enumerate(CLOUD_NATIVE_WORKLOAD_TYPES):
                name = WORKLOAD_DISPLAY_NAMES.get(wt, wt)
                console.print(f"  {i:>2}. {name} ({wt})")
            idx = IntPrompt.ask("Select number")
            if 0 <= idx < len(CLOUD_NATIVE_WORKLOAD_TYPES):
                explore_workload_type(CLOUD_NATIVE_WORKLOAD_TYPES[idx])
        elif choice == "3":
            idx = IntPrompt.ask("Event index (0 = most recent)", default=0)
            dump_raw_event(event_index=idx)
        elif choice == "4":
            explore_recent_events(hours=24, limit=100)
        elif choice == "5":
            explore_recent_events(hours=24, limit=100)
        elif choice == "6":
            hours = IntPrompt.ask("Hours to look back", default=72)
            explore_recent_events(hours=hours, limit=30)


if __name__ == "__main__":
    interactive_menu()