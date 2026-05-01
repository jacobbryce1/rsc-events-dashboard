"""
Test 4: Test the data collector and normalization logic.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from data_collector import EventDataCollector
from config import STATUS_CATEGORIES


def test_fetch_all_events():
    print("\n📦 Fetching all cloud native events (last 24h)...")
    print("   (This may take several minutes for large environments)\n")

    collector = EventDataCollector()
    events = collector.fetch_all_cloud_native_events()

    print(f"   ✅ Total events collected: {len(events)}")

    if not events:
        print("   ⚠️  No events found.")
        return events

    return events


def test_event_normalization(events=None):
    if events is None:
        collector = EventDataCollector()
        events = collector.fetch_all_cloud_native_events()

    if not events:
        print("\n📦 Skipping normalization test — no events")
        return

    print(f"\n📦 Validating normalization of {len(events)} events...")

    required_fields = [
        "id", "object_name", "object_id", "object_type", "object_type_display",
        "job_type", "raw_status", "status_category", "status_sort",
        "start_time_formatted", "elapsed_formatted",
        "data_transferred_formatted", "logical_size_formatted",
    ]

    sample = events[0]
    missing = [f for f in required_fields if f not in sample]
    if missing:
        print(f"   ❌ Missing fields: {missing}")
    else:
        print(f"   ✅ All {len(required_fields)} required fields present")

    valid_categories = set(STATUS_CATEGORIES.values()) | {"Unknown"}
    invalid = [(e["raw_status"], e["status_category"]) for e in events
               if e.get("status_category") not in valid_categories]

    if invalid:
        print(f"   ⚠️  {len(invalid)} events with unmapped status:")
        for raw, cat in set(invalid)[:5]:
            print(f"      raw='{raw}' → category='{cat}'")
    else:
        print(f"   ✅ All status values properly categorized")

    total = len(events)
    null_names = sum(1 for e in events if not e.get("object_name") or e["object_name"] == "N/A")
    null_ids = sum(1 for e in events if not e.get("object_id") or e["object_id"] == "N/A")
    null_start = sum(1 for e in events if not e.get("start_time_formatted") or e["start_time_formatted"] == "N/A")
    has_data = sum(1 for e in events if e.get("data_transferred_formatted") != "N/A")
    has_size = sum(1 for e in events if e.get("logical_size_formatted") != "N/A")

    print(f"\n   📋 Data Quality Report:")
    print(f"      Object Name populated:     {total - null_names}/{total} ({(total-null_names)/total*100:.0f}%)")
    print(f"      Object ID populated:       {total - null_ids}/{total} ({(total-null_ids)/total*100:.0f}%)")
    print(f"      Start Time populated:      {total - null_start}/{total} ({(total-null_start)/total*100:.0f}%)")
    print(f"      Data Transferred known:    {has_data}/{total} ({has_data/total*100:.0f}%)")
    print(f"      Logical Size known:        {has_size}/{total} ({has_size/total*100:.0f}%)")


def test_status_distribution(events=None):
    if events is None:
        collector = EventDataCollector()
        events = collector.fetch_all_cloud_native_events()

    if not events:
        print("\n📦 Skipping distribution test — no events")
        return

    print(f"\n📦 Status Distribution:")

    from collections import Counter
    counts = Counter(e.get("status_category", "Unknown") for e in events)

    priority = ["In Progress", "Queued", "Failed", "Partial", "Canceled", "Completed", "Unknown"]
    for status in priority:
        count = counts.get(status, 0)
        if count > 0:
            bar = "█" * min(count, 50)
            print(f"   {status:<15} {count:>5}  {bar}")


def test_workload_distribution(events=None):
    if events is None:
        collector = EventDataCollector()
        events = collector.fetch_all_cloud_native_events()

    if not events:
        print("\n📦 Skipping workload distribution — no events")
        return

    print(f"\n📦 Workload Type Distribution:")

    from collections import Counter
    counts = Counter(e.get("object_type_display", "Unknown") for e in events)

    for workload, count in counts.most_common():
        bar = "█" * min(count, 50)
        print(f"   {workload:<45} {count:>5}  {bar}")


def test_sort_order(events=None):
    if events is None:
        collector = EventDataCollector()
        events = collector.fetch_all_cloud_native_events()

    if not events:
        print("\n📦 Skipping sort test — no events")
        return

    print(f"\n📦 Validating sort order...")

    prev = -1
    out_of_order = 0
    for i, event in enumerate(events):
        curr = event.get("status_sort", 99)
        if curr < prev:
            out_of_order += 1
            if out_of_order <= 3:
                print(f"   ⚠️  Event {i}: {event['status_category']} (sort={curr}) after {prev}")
        prev = curr

    if out_of_order == 0:
        print(f"   ✅ All {len(events)} events correctly sorted by status priority")
    else:
        print(f"   ⚠️  {out_of_order} events out of sort order")

    print(f"\n   First events by category:")
    seen = set()
    for event in events:
        cat = event["status_category"]
        if cat not in seen:
            seen.add(cat)
            print(f"   {cat:<15} → {event['object_name']} ({event['job_type']})")


if __name__ == "__main__":
    print("=" * 60)
    print("DATA COLLECTION TESTS")
    print("=" * 60)

    events = test_fetch_all_events()
    test_event_normalization(events)
    test_status_distribution(events)
    test_workload_distribution(events)
    test_sort_order(events)

    print(f"\n{'='*60}")
    print("✅ Data collection tests complete.")
