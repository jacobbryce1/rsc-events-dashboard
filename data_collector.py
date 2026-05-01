import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable

from rsc_client import RSCClient
from config import (
    FILTERABLE_WORKLOAD_TYPES,
    UNFILTERABLE_CLOUD_TYPES,
    ALL_CLOUD_NATIVE_TYPES,
    STATUS_CATEGORIES,
    STATUS_SORT_ORDER,
    WORKLOAD_DISPLAY_NAMES,
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
            id
            fid
            activitySeriesId
            lastUpdated
            lastActivityType
            lastActivityStatus
            objectId
            objectName
            objectType
            severity
            startTime
            lastUpdated
            progress
            dataTransferred
            logicalSize
            effectiveThroughput
            location
            cluster {
                id
                name
            }
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""


class EventDataCollector:
    """
    Parallel event collector for RSC cloud native workloads.

    - Fetches filterable types in parallel threads
    - Fetches unfilterable types via chunked unfiltered scan
    - Shared RSCClient with connection pooling
    - Progress reporting via callback
    """

    def __init__(
        self,
        max_workers: int = 8,
        page_size: int = 200,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.client = RSCClient(max_connections=max_workers + 2)
        self.max_workers = max_workers
        self.page_size = page_size
        self._progress = progress_callback or (lambda msg: None)

    def fetch_all_cloud_native_events(self) -> List[Dict[str, Any]]:
        """
        Parallel two-pass collection:
        1. ThreadPool for each filterable type
        2. Parallel chunked scan for unfilterable types
        """
        start_time, end_time = get_24h_window()
        overall_start = time.time()

        self._progress("Starting parallel data collection...")

        # ── Pass 1: Parallel filtered fetches ──
        filtered_events = self._fetch_filtered_parallel(start_time, end_time)
        self._progress(
            f"Pass 1 complete: {len(filtered_events)} events from "
            f"{len(FILTERABLE_WORKLOAD_TYPES)} filterable types"
        )

        # ── Pass 2: Unfiltered scan for PascalCase types ──
        # Collect IDs from pass 1 to avoid scanning what we already have
        seen_ids = {
            e.get("activity_series_id") or e.get("id")
            for e in filtered_events
        }

        unfilterable_events = self._fetch_unfilterable_parallel(
            start_time, end_time, seen_ids
        )
        self._progress(
            f"Pass 2 complete: {len(unfilterable_events)} additional events "
            f"from unfilterable types"
        )

        # ── Combine and deduplicate ──
        all_events = filtered_events + unfilterable_events

        unique_events = []
        final_ids = set()
        for event in all_events:
            eid = event.get("activity_series_id") or event.get("id")
            if eid and eid not in final_ids:
                final_ids.add(eid)
                unique_events.append(event)

        # ── Sort ──
        unique_events.sort(
            key=lambda e: (
                STATUS_SORT_ORDER.get(e.get("raw_status", ""), 99),
                -(e.get("start_timestamp") or 0),
            )
        )

        elapsed = time.time() - overall_start
        self._progress(
            f"Collection complete: {len(unique_events)} unique events in {elapsed:.1f}s"
        )
        logger.info(
            f"Total: {len(unique_events)} events in {elapsed:.1f}s "
            f"({len(FILTERABLE_WORKLOAD_TYPES)} filtered + unfiltered scan)"
        )

        return unique_events

    # ─────────────────────────────────────────────────────────────
    # Pass 1: Parallel filtered fetches
    # ─────────────────────────────────────────────────────────────

    def _fetch_filtered_parallel(
        self, start_time: str, end_time: str
    ) -> List[Dict[str, Any]]:
        """Fetch all filterable workload types in parallel."""
        all_events = []
        errors = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_type = {
                executor.submit(
                    self._fetch_single_filtered, wt, start_time, end_time
                ): wt
                for wt in FILTERABLE_WORKLOAD_TYPES
            }

            for future in as_completed(future_to_type):
                wt = future_to_type[future]
                display = WORKLOAD_DISPLAY_NAMES.get(wt, wt)
                try:
                    events = future.result()
                    all_events.extend(events)
                    if events:
                        self._progress(f"  ✅ {display}: {len(events)} events")
                    else:
                        self._progress(f"  ⬜ {display}: no events")
                except Exception as e:
                    errors.append((wt, str(e)))
                    self._progress(f"  ❌ {display}: {e}")

        if errors:
            logger.warning(f"{len(errors)} filterable types failed: {errors}")

        return all_events

    def _fetch_single_filtered(
        self, workload_type: str, start_time: str, end_time: str
    ) -> List[Dict[str, Any]]:
        """Fetch events for one filterable workload type."""
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
            page_size=self.page_size,
        )

        events = []
        for node in raw_nodes:
            normalized = self._normalize_event(node)
            if normalized:
                events.append(normalized)
        return events

    # ─────────────────────────────────────────────────────────────
    # Pass 2: Chunked unfiltered scan for PascalCase types
    # ─────────────────────────────────────────────────────────────

    def _fetch_unfilterable_parallel(
        self,
        start_time: str,
        end_time: str,
        already_seen_ids: set,
    ) -> List[Dict[str, Any]]:
        """
        Fetch ALL events without objectType filter, then match
        unfilterable PascalCase types client-side.

        Uses parallel page fetching for speed.
        """
        if not UNFILTERABLE_CLOUD_TYPES:
            return []

        unfilterable_set = set(UNFILTERABLE_CLOUD_TYPES)
        self._progress(
            f"Scanning for {len(unfilterable_set)} unfilterable types..."
        )

        # First, get the first page to determine total scope
        variables = {
            "filters": {
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
            page_size=self.page_size,
        )

        self._progress(f"  Scanned {len(raw_nodes)} total events")

        # Filter client-side
        events = []
        for node in raw_nodes:
            obj_type = node.get("objectType", "")
            if obj_type not in unfilterable_set:
                continue

            event_id = node.get("activitySeriesId") or node.get("fid") or node.get("id")
            if event_id in already_seen_ids:
                continue

            normalized = self._normalize_event(node)
            if normalized:
                events.append(normalized)

        self._progress(
            f"  Matched {len(events)} unfilterable cloud-native events"
        )
        return events

    # ─────────────────────────────────────────────────────────────
    # Normalization
    # ─────────────────────────────────────────────────────────────

    def _normalize_event(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            raw_status = node.get("lastActivityStatus", "UNKNOWN") or "UNKNOWN"
            status_category = STATUS_CATEGORIES.get(raw_status, None)
            if status_category is None:
                status_category = STATUS_CATEGORIES.get(
                    raw_status.upper(), "Unknown"
                )

            start_time_str = node.get("startTime")
            last_updated_str = node.get("lastUpdated")

            start_dt = self._parse_timestamp(start_time_str)
            last_updated_dt = self._parse_timestamp(last_updated_str)

            elapsed_seconds = None
            if start_dt and last_updated_dt:
                elapsed_seconds = (last_updated_dt - start_dt).total_seconds()
                if elapsed_seconds < 0:
                    elapsed_seconds = 0

            if status_category == "In Progress" and start_dt:
                now = datetime.now(timezone.utc)
                elapsed_seconds = (now - start_dt).total_seconds()

            raw_job_type = (node.get("lastActivityType") or "").upper()
            data_kw = ["BACKUP", "RECOVERY", "REPLICATION", "ARCHIVE",
                       "RESTORE", "EXPORT", "DOWNLOAD", "COPY"]
            is_data_job = any(kw in raw_job_type for kw in data_kw)

            data_transferred = self._parse_bytes(node.get("dataTransferred"))
            if data_transferred == 0 and not is_data_job:
                data_transferred = None

            logical_size = self._parse_bytes(node.get("logicalSize"))
            if logical_size == 0 and not is_data_job:
                logical_size = None

            throughput = self._parse_bytes(node.get("effectiveThroughput"))
            if throughput == 0:
                throughput = None

            actual_type = node.get("objectType") or ""
            display_name = WORKLOAD_DISPLAY_NAMES.get(actual_type, actual_type)

            cluster_info = node.get("cluster") or {}

            return {
                "id": node.get("fid") or node.get("id") or "N/A",
                "activity_series_id": node.get("activitySeriesId", ""),
                "object_name": node.get("objectName", "N/A"),
                "object_id": node.get("objectId", "N/A"),
                "object_type": actual_type,
                "object_type_display": display_name,
                "job_type": self._format_job_type(
                    node.get("lastActivityType", "UNKNOWN")
                ),
                "raw_job_type": node.get("lastActivityType", "UNKNOWN"),
                "raw_status": raw_status,
                "status_category": status_category,
                "status_sort": STATUS_SORT_ORDER.get(
                    raw_status,
                    STATUS_SORT_ORDER.get(
                        raw_status.upper() if raw_status else "", 99
                    ),
                ),
                "start_time": start_time_str,
                "start_time_formatted": (
                    start_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    if start_dt else "N/A"
                ),
                "start_timestamp": start_dt.timestamp() if start_dt else None,
                "last_updated": last_updated_str,
                "elapsed_seconds": elapsed_seconds,
                "elapsed_formatted": self._format_duration(elapsed_seconds),
                "progress": node.get("progress"),
                "data_transferred_bytes": data_transferred,
                "data_transferred_formatted": self._format_bytes(data_transferred),
                "logical_size_bytes": logical_size,
                "logical_size_formatted": self._format_bytes(logical_size),
                "throughput_formatted": (
                    f"{self._format_bytes(throughput)}/s"
                    if throughput else "N/A"
                ),
                "severity": node.get("severity", ""),
                "cluster_name": cluster_info.get("name", "RSC"),
                "cluster_id": cluster_info.get("id", ""),
                "location": node.get("location", ""),
                "last_message": self._get_last_message(node),
            }
        except Exception as e:
            logger.warning(f"Failed to normalize event: {e}")
            return None

    # ─────────────────────────────────────────────────────────────
    # Helpers (all static, thread-safe)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            try:
                dt = datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
                return dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return None

    @staticmethod
    def _format_job_type(job_type: str) -> str:
        if not job_type:
            return "Unknown"
        return job_type.replace("_", " ").title()

    @staticmethod
    def _format_duration(seconds: Optional[float]) -> str:
        if seconds is None:
            return "N/A"
        seconds = int(seconds)
        if seconds < 0:
            return "N/A"
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"

    @staticmethod
    def _parse_bytes(value) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                multipliers = {
                    "B": 1, "KB": 1024, "MB": 1024**2,
                    "GB": 1024**3, "TB": 1024**4,
                }
                v = value.upper().strip()
                for suffix, mult in multipliers.items():
                    if v.endswith(suffix):
                        try:
                            return int(float(v[:-len(suffix)].strip()) * mult)
                        except ValueError:
                            pass
        return None

    @staticmethod
    def _format_bytes(byte_count: Optional[int]) -> str:
        if byte_count is None:
            return "N/A"
        if byte_count == 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        idx = 0
        size = float(byte_count)
        while size >= 1024 and idx < len(units) - 1:
            size /= 1024
            idx += 1
        return f"{int(size)} B" if idx == 0 else f"{size:.2f} {units[idx]}"

    @staticmethod
    def _get_last_message(node: Dict[str, Any]) -> str:
        try:
            nodes = node.get("activityConnection", {}).get("nodes", [])
            if nodes:
                return nodes[0].get("message", "")
        except (TypeError, IndexError, KeyError):
            pass
        return ""
