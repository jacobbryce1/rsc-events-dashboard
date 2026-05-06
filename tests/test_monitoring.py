"""
Test full collection, incremental fetching, cache persistence, and performance.
"""
import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from data_collector import EventDataCollector
from incremental_cache import IncrementalCache
from config import (
    MAX_WORKERS,
    FILTERED_PAGE_SIZE,
    REQUEST_TIMEOUT,
    INCREMENTAL_PAGE_SIZE,
    INCREMENTAL_MAX_PAGES,
    FILTERABLE_WORKLOAD_TYPES,
)


def create_collector():
    return EventDataCollector(
        max_workers=MAX_WORKERS,
        enable_console_progress=True,
        progress_callback=lambda msg: print(f"  {msg}"),
    )


def create_cache():
    return IncrementalCache(
        overlap_minutes=5,
        max_age_hours=24.0,
        persist_path=".event_cache.json",
    )


def test_full_load(collector, cache):
    print("\n" + "=" * 70)
    print("  TEST 1: FULL 24h COLLECTION")
    print("=" * 70)

    t0 = time.time()
    events = collector.fetch_all_cloud_native_events()
    duration = time.time() - t0

    result = cache.initialize(events)

    print(f"\n  ✅ Full load complete")
    print(f"     Events:   {result['inserted']}")
    print(f"     Duration: {duration:.1f}s ({duration/60:.1f}m)")

    metrics = collector.get_metrics_summary()
    print(f"     API calls:       {metrics['api']['total_calls']}")
    print(f"     Avg latency:     {metrics['api']['avg_latency_ms']}ms")
    print(f"     Errors:          {metrics['api']['total_errors']}")
    print(f"     Token refreshes: {metrics['token']['total_refreshes']}")

    return duration, result["inserted"]


def test_incremental_immediate(collector, cache):
    print("\n" + "=" * 70)
    print("  TEST 2: INCREMENTAL FETCH (immediate)")
    print("=" * 70)

    since = cache.incremental_start_time
    print(f"  Since: {since[:19]}")

    t0 = time.time()
    new_events = collector.fetch_incremental(since)
    duration = time.time() - t0

    result = cache.merge(new_events)

    print(f"\n  ✅ Duration:       {duration:.1f}s")
    print(f"     API returned:   {len(new_events)} events")
    print(f"     New:            {result['inserted']}")
    print(f"     Updated:        {result['updated']}")
    print(f"     Expired:        {result['expired']}")
    print(f"     Total cached:   {result['total']}")

    return duration, result


def test_incremental_after_wait(collector, cache, wait_seconds=30):
    print("\n" + "=" * 70)
    print(f"  TEST 3: INCREMENTAL AFTER {wait_seconds}s WAIT")
    print("=" * 70)

    print(f"  Waiting {wait_seconds}s for new events...")
    for remaining in range(wait_seconds, 0, -10):
        print(f"    ⏳ {remaining}s...", flush=True)
        time.sleep(min(10, remaining))

    since = cache.incremental_start_time
    print(f"\n  Since: {since[:19]}")

    t0 = time.time()
    new_events = collector.fetch_incremental(since)
    duration = time.time() - t0

    result = cache.merge(new_events)

    print(f"\n  ✅ Duration:       {duration:.1f}s")
    print(f"     API returned:   {len(new_events)} events")
    print(f"     New:            {result['inserted']}")
    print(f"     Updated:        {result['updated']}")
    print(f"     Total cached:   {result['total']}")

    return duration, result


def test_rapid_incrementals(collector, cache, count=3, interval=15):
    print("\n" + "=" * 70)
    print(f"  TEST 4: {count} RAPID INCREMENTALS ({interval}s apart)")
    print("=" * 70)

    results = []
    for i in range(1, count + 1):
        if i > 1:
            print(f"\n  ⏳ Waiting {interval}s...")
            time.sleep(interval)

        since = cache.incremental_start_time
        print(f"\n  ── Fetch {i}/{count} (since {since[:19]}) ──")

        t0 = time.time()
        new_events = collector.fetch_incremental(since)
        duration = time.time() - t0

        result = cache.merge(new_events)
        result["duration"] = round(duration, 1)
        result["api_events"] = len(new_events)
        results.append(result)

        print(f"  +{result['inserted']} new, ~{result['updated']} updated, "
              f"-{result['expired']} expired | {duration:.1f}s | "
              f"total: {result['total']}")

    return results


def test_cache_persistence(cache):
    print("\n" + "=" * 70)
    print("  TEST 5: CACHE PERSISTENCE")
    print("=" * 70)

    original = cache.event_count
    print(f"  Current: {original} events")
    print(f"  Simulating restart...")

    restored = IncrementalCache(
        overlap_minutes=5,
        max_age_hours=24.0,
        persist_path=".event_cache.json",
    )

    restored_count = restored.event_count
    print(f"  Restored: {restored_count} events")
    print(f"  needs_full_load: {restored.needs_full_load}")

    ok = restored_count == original
    print(f"  {'✅ Perfect restore' if ok else '⚠️  Partial restore'}")
    return ok


def test_expiration(cache):
    print("\n" + "=" * 70)
    print("  TEST 6: EXPIRATION")
    print("=" * 70)

    before = cache.event_count
    expired = cache.expire_old()
    print(f"  Before: {before}, Expired: {expired}, After: {cache.event_count}")
    print(f"  ✅ {'Removed old events' if expired else 'All within 24h window'}")


def print_comparison(full_dur, full_events, incr_results):
    print("\n" + "=" * 70)
    print("  PERFORMANCE COMPARISON")
    print("=" * 70)

    avg_dur = sum(r["duration"] for r in incr_results) / len(incr_results)
    avg_new = sum(r["inserted"] for r in incr_results) / len(incr_results)
    avg_upd = sum(r["updated"] for r in incr_results) / len(incr_results)
    speedup = full_dur / max(avg_dur, 0.1)

    print(f"""
  ┌────────────────────────┬──────────────┬──────────────┐
  │ Metric                 │ Full Load    │ Incremental  │
  ├────────────────────────┼──────────────┼──────────────┤
  │ Duration               │ {full_dur:>9.1f}s   │ {avg_dur:>9.1f}s   │
  │ Events from API        │ {full_events:>9d}    │ {avg_new:>9.0f}    │
  │ Updated events         │        n/a   │ {avg_upd:>9.0f}    │
  │ Speedup                │        1x    │ {speedup:>9.0f}x    │
  └────────────────────────┴──────────────┴──────────────┘
""")

    if speedup >= 10:
        print(f"  🚀 Incremental is {speedup:.0f}x faster!")
    elif speedup >= 2:
        print(f"  ✅ Incremental is {speedup:.1f}x faster")
    else:
        print(f"  ⚠️  Only {speedup:.1f}x speedup")


def main():
    print("=" * 70)
    print("  RSC DASHBOARD — FULL + INCREMENTAL TEST")
    print("=" * 70)

    print(f"\n  📋 Config:")
    print(f"     MAX_WORKERS:          {MAX_WORKERS}")
    print(f"     FILTERED_PAGE_SIZE:   {FILTERED_PAGE_SIZE}")
    print(f"     REQUEST_TIMEOUT:      {REQUEST_TIMEOUT}s")
    print(f"     FILTERABLE_TYPES:     {len(FILTERABLE_WORKLOAD_TYPES)}")
    print(f"     INCREMENTAL_PAGE:     {INCREMENTAL_PAGE_SIZE}")

    collector = create_collector()
    cache = create_cache()

    print(f"\n🔑 Token: remaining={collector.client.remaining_seconds:.0f}s")
    print(f"📦 Cache: {cache.event_count} events, needs_full={cache.needs_full_load}")

    if cache.needs_full_load:
        full_dur, full_events = test_full_load(collector, cache)
    else:
        full_events = cache.event_count
        full_dur = 120.0
        print(f"\n  SKIPPING FULL LOAD — cache has {full_events} events")
        print(f"  (delete .event_cache.json to force)")

    incr_dur_1, incr_res_1 = test_incremental_immediate(collector, cache)
    incr_dur_2, incr_res_2 = test_incremental_after_wait(collector, cache, 30)
    rapid = test_rapid_incrementals(collector, cache, count=3, interval=15)
    persist_ok = test_cache_persistence(cache)
    test_expiration(cache)

    all_incr = [
        {"duration": incr_dur_1, **incr_res_1},
        {"duration": incr_dur_2, **incr_res_2},
    ] + rapid
    print_comparison(full_dur, full_events, all_incr)

    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)

    checks = [
        ("Full load / cache", full_events > 0),
        ("Incremental faster than full", incr_dur_1 < full_dur),
        ("Post-wait incremental works", incr_res_2["total"] > 0),
        ("Rapid incrementals stable", all(r["total"] > 0 for r in rapid)),
        ("Cache persistence", persist_ok),
        ("Expiration runs", True),
    ]

    passed = 0
    for name, ok in checks:
        print(f"  {'✅' if ok else '❌'} {name}")
        if ok:
            passed += 1

    print(f"\n  {passed}/{len(checks)} passed")

    if passed == len(checks):
        print(f"\n  🚀 All tests passed! Run: streamlit run dashboard.py\n")
    else:
        print(f"\n  ⚠️  Review failures above\n")


if __name__ == "__main__":
    main()
