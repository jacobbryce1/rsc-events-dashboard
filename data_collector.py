"""
RSC Event Collector — single-pass filtered design.
All cloud-native types are now filterable.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable

from rsc_client import RSCClient
from token_monitor import MetricsStore, TokenMonitor, ConsoleReporter
from config import (
    FILTERABLE_WORKLOAD_TYPES,
    ALL_CLOUD_NATIVE_TYPES,
    STATUS_CATEGORIES,
    STATUS_SORT_ORDER,
    WORKLOAD_DISPLAY_NAMES,
    MAX_WORKERS,
    FILTERED_PAGE_SIZE,
    REQUEST_TIMEOUT,
    INCREMENTAL_PAGE_SIZE,
    INCREMENTAL_MAX_PAGES,
    get_24h_window,
)

logger = logging.getLogger(__name__)

EVENTS_QUERY = """
query CloudNativeEvents(
    $first: Int,
    $after: String,
    $filters: ActivitySeriesFilter,
    $sortBy: ActivitySeriesSortField,
    $sortOrder: SortOrder
) {
    activitySeriesConnection(
        first: $first,
        after: $after,
        filters: $filters,
        sortBy: $sortBy,
        sortOrder: $sortOrder
    ) {
        nodes {
            id fid activitySeriesId lastUpdated
            lastActivityType lastActivityStatus
            objectId objectName objectType
            severity startTime progress
            dataTransferred logicalSize effectiveThroughput
            location
            cluster { id name }
        }
        pageInfo { hasNextPage endCursor }
    }
}
"""


class EventDataCollector:
    def __init__(
        self,
        max_workers: int = MAX_WORKERS,
        progress_callback: Optional[Callable[[str], None]] = None,
        enable_console_progress: bool = False,
    ):
        self._metrics = MetricsStore()
        self._monitor = TokenMonitor(metrics_store=self._metrics)

        self.client = RSCClient(
            max_connections=max_workers + 2,
            timeout=REQUEST_TIMEOUT,
            monitor=self._monitor,
            metrics=self._metrics,
        )

        self.max_workers = max_workers
        self._progress_cb = progress_callback or (lambda msg: None)

        self._console = None
        if enable_console_progress:
            self._console = ConsoleReporter(self._metrics)

    def fetch_all_cloud_native_events(self) -> List[Dict[str, Any]]:
        start_time, end_time = get_24h_window()
        self._metrics.start_collection()

        type_count = len(FILTERABLE_WORKLOAD_TYPES)
        waves = (type_count + self.max_workers - 1) // self.max_workers
        est_seconds = waves * 35

        self._progress_cb(
            f"Full 24h collection: {type_count} types, "
            f"{self.max_workers} workers, ~{waves} waves, "
            f"~{est_seconds//60}m estimated"
        )

        try:
            all_events = []

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(
                        self._fetch_workload, wt, start_time, end_time
                    ): wt
                    for wt in FILTERABLE_WORKLOAD_TYPES
                }

                completed = 0
                failed = 0
                for future in as_completed(futures):
                    wt = futures[future]
                    display = WORKLOAD_DISPLAY_NAMES.get(wt, wt)
                    try:
                        events = future.result()
                        all_events.extend(events)
                        completed += 1
                        if events:
                            self._progress_cb(
                                f"  ✅ {display}: {len(events)} "
                                f"[{completed+failed}/{type_count}]"
                            )
                        else:
                            self._progress_cb(
                                f"  ⬜ {display}: 0 "
                                f"[{completed+failed}/{type_count}]"
                            )
                    except Exception as e:
                        failed += 1
                        self._progress_cb(
                            f"  ❌ {display}: {e} "
                            f"[{completed+failed}/{type_count}]"
                        )

                    if self._console:
                        self._console.update(self.client.remaining_seconds)

            unique = self._deduplicate_and_sort(all_events)

            elapsed = self._metrics.elapsed_seconds
            self._progress_cb(
                f"Complete: {len(unique)} unique events in "
                f"{elapsed:.0f}s ({elapsed/60:.1f}m)"
            )
            if failed:
                self._progress_cb(f"  ⚠️  {failed} types failed")

            return unique

        finally:
            self._metrics.end_collection()
            if self._console:
                self._console.final_report()

    def _fetch_workload(self, workload_type, start_time, end_time):
        variables = {
            "filters": {
                "objectType": [workload_type],
                "lastActivityType": [],
                "lastActivityStatus": [],
                "startTimeGt": start_time,
                "startTimeLt": end_time,
            },
            "sortBy": "START_TIME",
            "sortOrder": "DESC",
        }

        raw_nodes = self.client.execute_paginated_query(
            query=EVENTS_QUERY,
            variables=variables,
            data_path="activitySeriesConnection",
            page_size=FILTERED_PAGE_SIZE,
            workload_type=workload_type,
        )

        return [e for e in (self._normalize_event(n) for n in raw_nodes) if e]

    def fetch_incremental(
        self, since: str, end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if end_time is None:
            end_time = datetime.now(timezone.utc).isoformat()

        self._progress_cb(f"Incremental since {since[:19]}...")
        start = time.time()

        variables = {
            "filters": {
                "startTimeGt": since,
                "startTimeLt": end_time,
            },
            "sortBy": "START_TIME",
            "sortOrder": "DESC",
        }

        raw_nodes = self.client.execute_paginated_query(
            query=EVENTS_QUERY,
            variables=variables,
            data_path="activitySeriesConnection",
            page_size=INCREMENTAL_PAGE_SIZE,
            max_pages=INCREMENTAL_MAX_PAGES,
            workload_type="incremental",
        )

        events = []
        for node in raw_nodes:
            if node.get("objectType", "") in ALL_CLOUD_NATIVE_TYPES:
                normalized = self._normalize_event(node)
                if normalized:
                    events.append(normalized)

        unique = self._deduplicate_and_sort(events)
        elapsed = time.time() - start

        self._progress_cb(
            f"Incremental: scanned {len(raw_nodes)} → "
            f"{len(unique)} cloud-native in {elapsed:.1f}s"
        )
        return unique

    def _deduplicate_and_sort(self, events):
        seen = set()
        unique = []
        for e in events:
            eid = e.get("activity_series_id") or e.get("id")
            if eid and eid not in seen:
                seen.add(eid)
                unique.append(e)
        unique.sort(key=lambda e: (
            STATUS_SORT_ORDER.get(e.get("raw_status", ""), 99),
            -(e.get("start_timestamp") or 0),
        ))
        return unique

    def get_metrics_summary(self):
        return self._metrics.get_summary()

    def _normalize_event(self, node):
        try:
            raw_status = node.get("lastActivityStatus", "UNKNOWN") or "UNKNOWN"
            sc = STATUS_CATEGORIES.get(raw_status)
            if sc is None:
                sc = STATUS_CATEGORIES.get(raw_status.upper(), "Unknown")

            st_str = node.get("startTime")
            lu_str = node.get("lastUpdated")
            st_dt = self._parse_ts(st_str)
            lu_dt = self._parse_ts(lu_str)

            elapsed = None
            if st_dt and lu_dt:
                elapsed = max(0, (lu_dt - st_dt).total_seconds())
            if sc == "In Progress" and st_dt:
                elapsed = (datetime.now(timezone.utc) - st_dt).total_seconds()

            # End time: for completed/failed jobs, this is lastUpdated
            # For in-progress/queued jobs, end time is not yet known
            end_time_formatted = "N/A"
            if sc in ("Completed", "Failed", "Partial", "Canceled") and lu_dt:
                end_time_formatted = lu_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

            rjt = (node.get("lastActivityType") or "").upper()
            is_data = any(k in rjt for k in
                ["BACKUP", "RECOVERY", "REPLICATION", "ARCHIVE",
                 "RESTORE", "EXPORT", "DOWNLOAD", "COPY"])

            dt = self._pb(node.get("dataTransferred"))
            if dt == 0 and not is_data:
                dt = None
            ls = self._pb(node.get("logicalSize"))
            if ls == 0 and not is_data:
                ls = None
            tp = self._pb(node.get("effectiveThroughput"))
            if tp == 0:
                tp = None

            ot = node.get("objectType") or ""
            cl = node.get("cluster") or {}

            return {
                "id": node.get("fid") or node.get("id") or "N/A",
                "activity_series_id": node.get("activitySeriesId", ""),
                "object_name": node.get("objectName", "N/A"),
                "object_id": node.get("objectId", "N/A"),
                "object_type": ot,
                "object_type_display": WORKLOAD_DISPLAY_NAMES.get(ot, ot),
                "job_type": (node.get("lastActivityType") or "Unknown").replace("_", " ").title(),
                "raw_job_type": node.get("lastActivityType", "UNKNOWN"),
                "raw_status": raw_status,
                "status_category": sc,
                "status_sort": STATUS_SORT_ORDER.get(
                    raw_status,
                    STATUS_SORT_ORDER.get(raw_status.upper() if raw_status else "", 99),
                ),
                "start_time": st_str,
                "start_time_formatted": (
                    st_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if st_dt else "N/A"
                ),
                "start_timestamp": st_dt.timestamp() if st_dt else None,
                "end_time_formatted": end_time_formatted,
                "last_updated": lu_str,
                "elapsed_seconds": elapsed,
                "elapsed_formatted": self._fd(elapsed),
                "progress": node.get("progress"),
                "data_transferred_bytes": dt,
                "data_transferred_formatted": self._fb(dt),
                "logical_size_bytes": ls,
                "logical_size_formatted": self._fb(ls),
                "throughput_formatted": f"{self._fb(tp)}/s" if tp else "N/A",
                "severity": node.get("severity", ""),
                "cluster_name": cl.get("name", "RSC"),
                "cluster_id": cl.get("id", ""),
                "location": node.get("location", ""),
                "last_message": self._glm(node),
            }
        except Exception as e:
            logger.warning(f"Normalize failed: {e}")
            return None

    @staticmethod
    def _parse_ts(ts):
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            try:
                return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return None

    @staticmethod
    def _fd(s):
        if s is None:
            return "N/A"
        s = int(s)
        if s < 0:
            return "N/A"
        if s < 60:
            return f"{s}s"
        if s < 3600:
            return f"{s // 60}m {s % 60}s"
        return f"{s // 3600}h {(s % 3600) // 60}m"

    @staticmethod
    def _pb(v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _fb(b):
        if b is None:
            return "N/A"
        if b == 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        s = float(b)
        while s >= 1024 and i < 4:
            s /= 1024
            i += 1
        return f"{int(s)} B" if i == 0 else f"{s:.2f} {units[i]}"

    @staticmethod
    def _glm(node):
        try:
            ns = node.get("activityConnection", {}).get("nodes", [])
            return ns[0].get("message", "") if ns else ""
        except (TypeError, IndexError, KeyError):
            return ""
