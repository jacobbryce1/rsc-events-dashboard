"""
Test 3: Validate each GraphQL query returns expected structure.
"""
import sys
import os
import json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from rsc_client import RSCClient
from config import (
    FILTERABLE_WORKLOAD_TYPES,
    UNFILTERABLE_CLOUD_TYPES,
    WORKLOAD_DISPLAY_NAMES,
    get_24h_window,
)


def test_activity_series_schema():
    print("\n📊 Testing activitySeriesConnection schema...")

    client = RSCClient()
    start_time, end_time = get_24h_window()

    query = """
    query SchemaTest($first: Int, $filters: ActivitySeriesFilter) {
        activitySeriesConnection(first: $first, filters: $filters) {
            nodes {
                id fid activitySeriesId
                lastActivityType lastActivityStatus
                objectId objectName objectType
                startTime lastUpdated progress
                dataTransferred logicalSize effectiveThroughput
                location severity
                cluster { id name }
            }
            pageInfo { hasNextPage endCursor }
        }
    }
    """

    variables = {
        "first": 5,
        "filters": {
            "startTimeGt": start_time,
            "startTimeLt": end_time,
        },
    }

    result = client.execute_query(query, variables)
    connection = result.get("activitySeriesConnection", {})

    assert "nodes" in connection, "Missing 'nodes' in response"
    assert "pageInfo" in connection, "Missing 'pageInfo' in response"

    nodes = connection["nodes"]
    print(f"   ✅ Query returned {len(nodes)} events")

    if nodes:
        node = nodes[0]
        expected_fields = [
            "id", "lastActivityType", "lastActivityStatus",
            "objectId", "objectName", "objectType", "startTime", "lastUpdated",
        ]
        present = [f for f in expected_fields if f in node and node[f] is not None]
        missing = [f for f in expected_fields if f not in node or node[f] is None]

        print(f"   ✅ Present fields: {', '.join(present)}")
        if missing:
            print(f"   ⚠️  Null/missing: {', '.join(missing)}")

        print(f"\n   📋 Sample event:")
        print(f"      Object: {node.get('objectName')}")
        print(f"      Type:   {node.get('objectType')}")
        print(f"      Status: {node.get('lastActivityStatus')}")
        print(f"      Job:    {node.get('lastActivityType')}")
        print(f"      Start:  {node.get('startTime')}")

        print(f"\n   📋 Optional field availability:")
        for field in ["dataTransferred", "logicalSize", "effectiveThroughput", "progress", "location"]:
            value = node.get(field)
            status = "✅ populated" if value is not None else "⬜ null"
            print(f"      {field}: {status} ({value})")


def test_discover_active_workload_types():
    print("\n📊 Testing filterable workload types...")
    print(f"   ({len(FILTERABLE_WORKLOAD_TYPES)} filterable types to test)\n")

    client = RSCClient()
    start_time, end_time = get_24h_window()

    query = """
    query WorkloadTest($first: Int, $filters: ActivitySeriesFilter) {
        activitySeriesConnection(first: $first, filters: $filters) {
            nodes { id objectType }
            pageInfo { hasNextPage }
        }
    }
    """

    active = []
    empty = []
    errors = []

    for wt in FILTERABLE_WORKLOAD_TYPES:
        display = WORKLOAD_DISPLAY_NAMES.get(wt, wt)
        try:
            variables = {
                "first": 1,
                "filters": {
                    "objectType": [wt],
                    "startTimeGt": start_time,
                    "startTimeLt": end_time,
                },
            }
            result = client.execute_query(query, variables)
            nodes = result.get("activitySeriesConnection", {}).get("nodes", [])
            has_more = result.get("activitySeriesConnection", {}).get("pageInfo", {}).get("hasNextPage", False)

            if nodes:
                count = "1+" if has_more else str(len(nodes))
                active.append(wt)
                print(f"   ✅ {display:<40} {count} events")
            else:
                empty.append(wt)
                print(f"   ⬜ {display:<40} no events")
        except Exception as e:
            errors.append(wt)
            print(f"   ❌ {display:<40} error: {e}")

    # Test unfilterable types via unfiltered query
    print(f"\n📊 Testing unfilterable (PascalCase) types via unfiltered scan...")
    print(f"   ({len(UNFILTERABLE_CLOUD_TYPES)} types to check)\n")

    unfiltered_query = """
    query($first: Int, $filters: ActivitySeriesFilter) {
        activitySeriesConnection(first: $first, filters: $filters, sortBy: START_TIME, sortOrder: DESC) {
            nodes { objectType objectName }
            pageInfo { hasNextPage endCursor }
        }
    }
    """

    variables = {
        "first": 200,
        "filters": {
            "startTimeGt": start_time,
            "startTimeLt": end_time,
        },
    }

    result = client.execute_query(unfiltered_query, variables)
    nodes = result.get("activitySeriesConnection", {}).get("nodes", [])

    types_found = {}
    for node in nodes:
        ot = node.get("objectType", "")
        if ot not in types_found:
            types_found[ot] = {"count": 0, "sample": node.get("objectName")}
        types_found[ot]["count"] += 1

    for ut in UNFILTERABLE_CLOUD_TYPES:
        display = WORKLOAD_DISPLAY_NAMES.get(ut, ut)
        if ut in types_found:
            info = types_found[ut]
            print(f"   ✅ {display:<40} {info['count']} events (sample: {info['sample']})")
        else:
            print(f"   ⬜ {display:<40} not seen in first 200 events")

    print(f"\n{'='*60}")
    print(f"   Filterable — active: {len(active)}, empty: {len(empty)}, errors: {len(errors)}")

    assert len(errors) == 0, f"{len(errors)} filterable types returned errors: {errors}"


def test_filter_by_status():
    print("\n📊 Testing status-based filtering...")

    client = RSCClient()
    start_time, end_time = get_24h_window()

    # Use values discovered from the actual API
    statuses_to_test = ["Running", "Queued", "Failure", "Success", "Canceled"]

    query = """
    query StatusTest($first: Int, $filters: ActivitySeriesFilter) {
        activitySeriesConnection(first: $first, filters: $filters) {
            nodes { id }
            pageInfo { hasNextPage }
        }
    }
    """

    for status in statuses_to_test:
        try:
            variables = {
                "first": 1,
                "filters": {
                    "lastActivityStatus": [status],
                    "startTimeGt": start_time,
                    "startTimeLt": end_time,
                },
            }
            result = client.execute_query(query, variables)
            nodes = result.get("activitySeriesConnection", {}).get("nodes", [])
            has_more = result.get("activitySeriesConnection", {}).get("pageInfo", {}).get("hasNextPage", False)
            count = "1+" if has_more else str(len(nodes))
            emoji = "✅" if nodes else "⬜"
            print(f"   {emoji} {status:<15} {count} events")
        except Exception as e:
            print(f"   ❌ {status:<15} error: {e}")


def test_pagination():
    print("\n📊 Testing pagination...")

    client = RSCClient()
    start_time, end_time = get_24h_window()

    query = """
    query PaginationTest($first: Int, $after: String, $filters: ActivitySeriesFilter) {
        activitySeriesConnection(first: $first, after: $after, filters: $filters) {
            nodes { id objectName }
            pageInfo { hasNextPage endCursor }
        }
    }
    """

    variables = {
        "first": 3,
        "after": None,
        "filters": {
            "startTimeGt": start_time,
            "startTimeLt": end_time,
        },
    }

    result = client.execute_query(query, variables)
    conn = result.get("activitySeriesConnection", {})
    page1 = conn.get("nodes", [])
    pi = conn.get("pageInfo", {})

    print(f"   ✅ Page 1: {len(page1)} events")

    if pi.get("hasNextPage") and pi.get("endCursor"):
        variables["after"] = pi["endCursor"]
        result2 = client.execute_query(query, variables)
        page2 = result2.get("activitySeriesConnection", {}).get("nodes", [])
        print(f"   ✅ Page 2: {len(page2)} events")

        ids1 = {n["id"] for n in page1}
        ids2 = {n["id"] for n in page2}
        overlap = ids1 & ids2
        if overlap:
            print(f"   ⚠️  Overlapping IDs: {len(overlap)}")
        else:
            print(f"   ✅ No duplicate events between pages")
    else:
        print(f"   ⬜ Only one page — pagination not tested")


if __name__ == "__main__":
    tests = [
        test_activity_series_schema,
        test_discover_active_workload_types,
        test_filter_by_status,
        test_pagination,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Query Validation: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
    print("✅ All query tests passed. Proceed to data collection tests.")
