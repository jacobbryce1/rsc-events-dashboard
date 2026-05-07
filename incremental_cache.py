"""
incremental_cache.py — Rolling 24 h event cache with optional encrypted persistence.

Security fixes applied:
  F-003: Disk cache is now encrypted at rest using Fernet symmetric encryption
         (cryptography package).  A random 256-bit key is generated on first run
         and stored in a separate key file whose permissions are set to 0o600
         (owner read/write only) immediately after creation.  The cache data
         file is written as opaque ciphertext; without the key file it cannot be
         read.  If the key file is absent the cache falls back to an in-memory
         only mode rather than writing plaintext.

         New constructor parameter:
           key_path (str | None): path for the encryption key file.
                                  Default: ".cache.key"
                                  Set to None to disable disk persistence entirely.

         Backwards-compatible: existing code that passes persist_path= still
         works; encrypted mode is the default when both persist_path and
         key_path are non-None.

Dependencies added to requirements.txt:
    cryptography>=42.0.0
"""

import os
import stat
import time
import threading
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Optional encrypted persistence ──────────────────────────────────────────

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography package not installed — disk cache persistence is disabled. "
        "Run: pip install 'cryptography>=42.0.0'"
    )


def _load_or_create_key(key_path: Path) -> Optional[bytes]:
    """
    Load an existing Fernet key from *key_path* or generate and save a new one.
    The key file is created with mode 0o600 (owner read/write only).
    Returns the raw key bytes, or None if the key could not be provisioned.
    """
    if not _CRYPTO_AVAILABLE:
        return None

    if key_path.exists():
        try:
            return key_path.read_bytes().strip()
        except OSError as exc:
            logger.warning("Cannot read cache key file %s: %s", key_path, exc)
            return None

    # Generate a fresh key and save it with restrictive permissions
    try:
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        # Restrict to owner read/write only (ignored on Windows)
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
        logger.info("Generated new cache encryption key: %s", key_path)
        return key
    except OSError as exc:
        logger.warning("Cannot create cache key file %s: %s — disabling disk cache", key_path, exc)
        return None


class IncrementalCache:
    """
    Maintains a rolling 24 h window of events with incremental updates.

    Lifecycle:
      1. First call: full 24 h scan, populate cache
      2. Subsequent calls: fetch only new events since last update
      3. Each update: merge new, update changed, expire old
      4. Optional: persist to encrypted disk file for restart recovery

    Usage::

        cache = IncrementalCache()

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
        persist_path: Optional[str] = ".event_cache.bin",  # F-003: .bin not .json
        key_path: Optional[str] = ".cache.key",             # F-003: separate key file
        expire_interval_seconds: float = 300.0,
    ):
        self._lock = threading.RLock()

        # Configuration
        self._overlap_minutes = overlap_minutes
        self._max_age = timedelta(hours=max_age_hours)
        self._persist_path = Path(persist_path) if persist_path else None
        self._expire_interval = expire_interval_seconds

        # F-003: encryption key (None → no disk persistence)
        self._fernet = None
        if self._persist_path and key_path and _CRYPTO_AVAILABLE:
            key = _load_or_create_key(Path(key_path))
            if key:
                self._fernet = Fernet(key)
            else:
                logger.warning(
                    "Cache encryption key unavailable — disk persistence disabled."
                )

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

    # ─────────────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def needs_full_load(self) -> bool:
        if not self._initialized_at:
            return True
        age = time.time() - self._initialized_at
        if age > self._max_age.total_seconds():
            return True
        if len(self._events) == 0:
            return True
        return False

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def incremental_start_time(self) -> str:
        if self._last_incremental:
            ref_time = self._last_incremental
        elif self._last_full_load:
            ref_time = self._last_full_load
        else:
            return (datetime.now(timezone.utc) - self._max_age).isoformat()

        overlap = timedelta(minutes=self._overlap_minutes)
        start = datetime.fromtimestamp(ref_time, tz=timezone.utc) - overlap
        return start.isoformat()

    @property
    def last_update_age_seconds(self) -> float:
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
            "disk_encrypted": self._fernet is not None,  # F-003: visible in metrics
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Core Operations
    # ─────────────────────────────────────────────────────────────────────────

    def initialize(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Full load: replace entire cache with provided events."""
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

            logger.info("Cache initialized with %d events", inserted)
            self._persist_to_disk()
            return {"inserted": inserted, "total": len(self._events)}

    def merge(self, new_events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Incremental merge: add new events, update existing, expire old."""
        with self._lock:
            inserted = 0
            updated = 0
            for event in new_events:
                eid = event.get("activity_series_id") or event.get("id")
                if not eid:
                    continue
                if eid in self._events:
                    if self._event_changed(self._events[eid], event):
                        self._events[eid] = event
                        updated += 1
                else:
                    self._events[eid] = event
                    inserted += 1

            self._last_incremental = time.time()
            self._incremental_count += 1
            self._total_inserts += inserted
            self._total_updates += updated

            expired = self._maybe_expire()

            logger.info(
                "Incremental merge: +%d new, ~%d updated, -%d expired, =%d total",
                inserted, updated, expired, len(self._events),
            )

            if self._incremental_count % 5 == 0:
                self._persist_to_disk()

            return {
                "inserted": inserted,
                "updated": updated,
                "expired": expired,
                "total": len(self._events),
            }

    def get_all_events(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events.values())

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        return self._events.get(event_id)

    def expire_old(self) -> int:
        with self._lock:
            return self._do_expire()

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._initialized_at = None
            self._last_full_load = None
            self._last_incremental = None
            self._incremental_count = 0
            if self._persist_path and self._persist_path.exists():
                self._persist_path.unlink()
            logger.info("Cache cleared.")

    # ─────────────────────────────────────────────────────────────────────────
    # Expiration
    # ─────────────────────────────────────────────────────────────────────────

    def _maybe_expire(self) -> int:
        now = time.time()
        if now - self._last_expire < self._expire_interval:
            return 0
        self._last_expire = now
        return self._do_expire()

    def _do_expire(self) -> int:
        cutoff = datetime.now(timezone.utc) - self._max_age
        cutoff_ts = cutoff.timestamp()
        expired_ids = [
            eid for eid, event in self._events.items()
            if (ts := event.get("start_timestamp")) and ts < cutoff_ts
        ]
        for eid in expired_ids:
            del self._events[eid]
        if expired_ids:
            self._total_expired += len(expired_ids)
            logger.info("Expired %d events older than %s", len(expired_ids), self._max_age)
        return len(expired_ids)

    # ─────────────────────────────────────────────────────────────────────────
    # Change Detection
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _event_changed(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
        for key in ("raw_status", "status_category", "progress",
                    "last_updated", "data_transferred_bytes"):
            if old.get(key) != new.get(key):
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Disk Persistence  (F-003: encrypted)
    # ─────────────────────────────────────────────────────────────────────────

    def _persist_to_disk(self) -> None:
        """
        Save cache to disk.

        F-003: If a Fernet instance is available the payload is JSON-serialised
        and then AES-128-CBC encrypted before writing.  Without the key file the
        ciphertext cannot be decoded.  Falls back to no-op if encryption is
        unavailable.
        """
        if not self._persist_path or not self._fernet:
            if self._persist_path and not self._fernet:
                logger.debug("Skipping disk persist — encryption unavailable.")
            return

        try:
            data = {
                "initialized_at": self._initialized_at,
                "last_full_load": self._last_full_load,
                "last_incremental": self._last_incremental,
                "incremental_count": self._incremental_count,
                "events": self._events,
            }
            plaintext = json.dumps(data, default=str).encode()
            ciphertext = self._fernet.encrypt(plaintext)

            tmp = self._persist_path.with_suffix(".tmp")
            tmp.write_bytes(ciphertext)
            # Set restrictive permissions on the cache file too
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
            tmp.rename(self._persist_path)

        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist cache: %s", exc)

    def _restore_from_disk(self) -> None:
        """
        Restore cache from disk if available and fresh.

        F-003: Decrypts using the Fernet key before JSON-parsing.  An
        InvalidToken exception (wrong key / tampered data) is caught and
        treated as a cache miss — the cache starts fresh.
        """
        if not self._persist_path or not self._persist_path.exists():
            return
        if not self._fernet:
            logger.info(
                "Encrypted cache file present but no key — starting fresh. "
                "Delete %s if you want to use unencrypted mode.",
                self._persist_path,
            )
            return

        try:
            ciphertext = self._persist_path.read_bytes()
            plaintext = self._fernet.decrypt(ciphertext)
            data = json.loads(plaintext.decode())

            restored_at = data.get("initialized_at", 0)
            age = time.time() - restored_at
            if age > self._max_age.total_seconds():
                logger.info("Cached data on disk is too old (%dm). Starting fresh.", age // 60)
                return

            self._initialized_at = data.get("initialized_at")
            self._last_full_load = data.get("last_full_load")
            self._last_incremental = data.get("last_incremental")
            self._incremental_count = data.get("incremental_count", 0)
            self._events = data.get("events", {})

            logger.info(
                "Restored %d events from encrypted disk cache (age: %dm)",
                len(self._events), age // 60,
            )

        except (ImportError,) as exc:
            logger.warning("Fernet not available: %s", exc)
        except Exception as exc:  # noqa: BLE001 — includes InvalidToken, JSONDecodeError, OSError
            logger.warning(
                "Failed to restore cache (wrong key, corrupt file, or IO error): %s — "
                "starting fresh.", exc,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _format_ts(ts: Optional[float]) -> Optional[str]:
        if not ts:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
