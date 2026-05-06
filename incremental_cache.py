"""
Incremental event cache with rolling 24h window.

After the initial full load, only fetches new/changed events.
Automatically expires events older than 24 hours.
Thread-safe for use with Streamlit's caching.
"""
import time
import threading
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class IncrementalCache:
    """
    Maintains a rolling 24h window of events with incremental updates.

    Lifecycle:
        1. First call: full 24h scan, populate cache
        2. Subsequent calls: fetch only new events since last update
        3. Each update: merge new, update changed, expire old
        4. Optional: persist to disk for restart recovery

    Usage:
        cache = IncrementalCache()

        # In dashboard refresh loop:
        if cache.needs_full_load:
            events = collector.fetch_all_cloud_native_events()
            cache.initialize(events)
        else:
            new_events = collector.fetch_incremental(cache.incremental_start_time)
            cache.merge(new_events)

        df = cache.get_dataframe()
    """

    def __init__(
        self,
        overlap_minutes: int = 5,
        max_age_hours: float = 24.0,
        persist_path: Optional[str] = ".event_cache.json",
        expire_interval_seconds: float = 300.0,
    ):
        self._lock = threading.RLock()

        # Configuration
        self._overlap_minutes = overlap_minutes
        self._max_age = timedelta(hours=max_age_hours)
        self._persist_path = Path(persist_path) if persist_path else None
        self._expire_interval = expire_interval_seconds

        # Event storage: keyed by activity_series_id for O(1) upsert
        self._events: Dict[str, Dict[str, Any]] = {}

        # Timestamps
        self._initialized_at: Optional[float] = None
        self._last_full_load: Optional[float] = None
        self._last_incremental: Optional[float] = None
        self._last_expire: float = 0

        # Metrics
        self._total_inserts: int = 0
        self._total_updates: int = 0
        self._total_expired: int = 0
        self._incremental_count: int = 0

        # Try to restore from disk
        self._restore_from_disk()

    # ─────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────

    @property
    def needs_full_load(self) -> bool:
        """True if cache is empty or too old for incremental updates."""
        if not self._initialized_at:
            return True
        # Force full reload if cache is older than max_age
        age = time.time() - self._initialized_at
        if age > self._max_age.total_seconds():
            return True
        # Force full reload if no events at all
        if len(self._events) == 0:
            return True
        return False

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def incremental_start_time(self) -> str:
        """
        ISO timestamp to use as startTimeGt for incremental fetch.
        Uses last update time minus overlap to catch any events
        that arrived between fetches.
        """
        if self._last_incremental:
            ref_time = self._last_incremental
        elif self._last_full_load:
            ref_time = self._last_full_load
        else:
            # Fallback: 24 hours ago
            return (
                datetime.now(timezone.utc) - self._max_age
            ).isoformat()

        overlap = timedelta(minutes=self._overlap_minutes)
        start = datetime.fromtimestamp(ref_time, tz=timezone.utc) - overlap
        return start.isoformat()

    @property
    def last_update_age_seconds(self) -> float:
        """Seconds since last successful update (full or incremental)."""
        last = self._last_incremental or self._last_full_load
        if not last:
            return float("inf")
        return time.time() - last

    @property
    def metrics(self) -> Dict[str, Any]:
        return {
            "event_count": len(self._events),
            "needs_full_load": self.needs_full_load,
            "initialized_at": self._format_ts(self._initialized_at),
            "last_full_load": self._format_ts(self._last_full_load),
            "last_incremental": self._format_ts(self._last_incremental),
            "last_update_age_s": round(self.last_update_age_seconds, 1),
            "incremental_fetches": self._incremental_count,
            "total_inserts": self._total_inserts,
            "total_updates": self._total_updates,
            "total_expired": self._total_expired,
        }

    # ─────────────────────────────────────────────────────────────
    # Core Operations
    # ─────────────────────────────────────────────────────────────

    def initialize(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Full load: replace entire cache with provided events.
        Called on first load or when cache is stale.
        """
        with self._lock:
            self._events.clear()

            inserted = 0
            for event in events:
                eid = event.get("activity_series_id") or event.get("id")
                if eid:
                    self._events[eid] = event
                    inserted += 1

            now = time.time()
            self._initialized_at = now
            self._last_full_load = now
            self._last_incremental = now
            self._total_inserts += inserted
            self._last_expire = now

            logger.info(f"Cache initialized with {inserted} events")
            self._persist_to_disk()

            return {"inserted": inserted, "total": len(self._events)}

    def merge(self, new_events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Incremental merge: add new events, update existing, expire old.

        Returns counts of what changed.
        """
        with self._lock:
            inserted = 0
            updated = 0

            for event in new_events:
                eid = event.get("activity_series_id") or event.get("id")
                if not eid:
                    continue

                if eid in self._events:
                    # Update existing event (status may have changed)
                    existing = self._events[eid]
                    if self._event_changed(existing, event):
                        self._events[eid] = event
                        updated += 1
                else:
                    # New event
                    self._events[eid] = event
                    inserted += 1

            self._last_incremental = time.time()
            self._incremental_count += 1
            self._total_inserts += inserted
            self._total_updates += updated

            # Periodically expire old events
            expired = self._maybe_expire()

            logger.info(
                f"Incremental merge: +{inserted} new, "
                f"~{updated} updated, -{expired} expired, "
                f"={len(self._events)} total"
            )

            # Persist less frequently for incremental updates
            if self._incremental_count % 5 == 0:
                self._persist_to_disk()

            return {
                "inserted": inserted,
                "updated": updated,
                "expired": expired,
                "total": len(self._events),
            }

    def get_all_events(self) -> List[Dict[str, Any]]:
        """Get all cached events as a list."""
        with self._lock:
            return list(self._events.values())

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a single event by ID."""
        return self._events.get(event_id)

    def expire_old(self) -> int:
        """Force expire events older than max_age."""
        with self._lock:
            return self._do_expire()

    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._events.clear()
            self._initialized_at = None
            self._last_full_load = None
            self._last_incremental = None
            self._incremental_count = 0

        if self._persist_path and self._persist_path.exists():
            self._persist_path.unlink()

        logger.info("Cache cleared.")

    # ─────────────────────────────────────────────────────────────
    # Expiration
    # ─────────────────────────────────────────────────────────────

    def _maybe_expire(self) -> int:
        """Expire old events if enough time has passed."""
        now = time.time()
        if now - self._last_expire < self._expire_interval:
            return 0
        self._last_expire = now
        return self._do_expire()

    def _do_expire(self) -> int:
        """Remove events older than max_age."""
        cutoff = datetime.now(timezone.utc) - self._max_age
        cutoff_ts = cutoff.timestamp()

        expired_ids = []
        for eid, event in self._events.items():
            event_ts = event.get("start_timestamp")
            if event_ts and event_ts < cutoff_ts:
                expired_ids.append(eid)

        for eid in expired_ids:
            del self._events[eid]

        if expired_ids:
            self._total_expired += len(expired_ids)
            logger.info(f"Expired {len(expired_ids)} events older than {self._max_age}")

        return len(expired_ids)

    # ─────────────────────────────────────────────────────────────
    # Change Detection
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _event_changed(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """Check if an event has meaningfully changed."""
        # Status change is the most important
        if old.get("raw_status") != new.get("raw_status"):
            return True
        if old.get("status_category") != new.get("status_category"):
            return True
        # Progress update
        if old.get("progress") != new.get("progress"):
            return True
        # Last updated changed
        if old.get("last_updated") != new.get("last_updated"):
            return True
        # Data transfer amount changed
        if old.get("data_transferred_bytes") != new.get("data_transferred_bytes"):
            return True
        return False

    # ─────────────────────────────────────────────────────────────
    # Disk Persistence
    # ─────────────────────────────────────────────────────────────

    def _persist_to_disk(self) -> None:
        """Save cache to disk for restart recovery."""
        if not self._persist_path:
            return

        try:
            data = {
                "initialized_at": self._initialized_at,
                "last_full_load": self._last_full_load,
                "last_incremental": self._last_incremental,
                "incremental_count": self._incremental_count,
                "events": self._events,
            }

            tmp = self._persist_path.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(data, f, default=str)
            tmp.rename(self._persist_path)

        except IOError as e:
            logger.warning(f"Failed to persist cache: {e}")

    def _restore_from_disk(self) -> None:
        """Restore cache from disk if available and fresh."""
        if not self._persist_path or not self._persist_path.exists():
            return

        try:
            with open(self._persist_path, "r") as f:
                data = json.load(f)

            restored_at = data.get("initialized_at", 0)
            age = time.time() - restored_at

            # Only restore if less than max_age old
            if age > self._max_age.total_seconds():
                logger.info("Cached data on disk is too old. Starting fresh.")
                return

            self._initialized_at = data.get("initialized_at")
            self._last_full_load = data.get("last_full_load")
            self._last_incremental = data.get("last_incremental")
            self._incremental_count = data.get("incremental_count", 0)
            self._events = data.get("events", {})

            logger.info(
                f"Restored {len(self._events)} events from disk "
                f"(age: {age/60:.0f}m)"
            )

        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.warning(f"Failed to restore cache: {e}")

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _format_ts(ts: Optional[float]) -> Optional[str]:
        if not ts:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
