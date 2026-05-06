"""
Token health monitoring with metrics collection, alerting, and reporting.

Features:
- Tracks every token refresh (success/failure/latency)
- Records API call metrics (count, errors, rate limits)
- Expiry countdown with configurable warning thresholds
- Thread-safe metrics store
- Live progress reporting for long-running collections
- Export metrics as dict, JSON, or structured log
"""
import time
import threading
import logging
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone
from collections import deque

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────

@dataclass
class TokenRefreshEvent:
    """Record of a single token refresh."""
    timestamp: float
    success: bool
    latency_ms: float
    remaining_before_refresh_s: float
    error: Optional[str] = None
    refresh_number: int = 0


@dataclass
class APICallEvent:
    """Record of a single API call."""
    timestamp: float
    workload_type: str
    page: int
    latency_ms: float
    status_code: int
    success: bool
    events_returned: int = 0
    error: Optional[str] = None


@dataclass
class RateLimitEvent:
    """Record of a rate limit hit."""
    timestamp: float
    retry_after_s: int
    workload_type: str


# ─────────────────────────────────────────────────────────────────
# Metrics Store
# ─────────────────────────────────────────────────────────────────

class MetricsStore:
    """Thread-safe metrics accumulator."""

    def __init__(self, max_history: int = 1000):
        self._lock = threading.Lock()
        self._max_history = max_history

        # Token metrics
        self.token_refreshes: deque = deque(maxlen=max_history)
        self.total_refreshes: int = 0
        self.total_refresh_failures: int = 0

        # API call metrics
        self.api_calls: deque = deque(maxlen=max_history)
        self.total_api_calls: int = 0
        self.total_api_errors: int = 0
        self.total_events_fetched: int = 0

        # Rate limit metrics
        self.rate_limits: deque = deque(maxlen=max_history)
        self.total_rate_limits: int = 0
        self.total_rate_limit_wait_s: float = 0

        # Timing
        self.collection_start_time: Optional[float] = None
        self.collection_end_time: Optional[float] = None

        # Per-workload tracking
        self.workload_stats: Dict[str, Dict[str, Any]] = {}

    def record_token_refresh(self, event: TokenRefreshEvent) -> None:
        with self._lock:
            self.token_refreshes.append(event)
            self.total_refreshes += 1
            if not event.success:
                self.total_refresh_failures += 1

    def record_api_call(self, event: APICallEvent) -> None:
        with self._lock:
            self.api_calls.append(event)
            self.total_api_calls += 1
            if not event.success:
                self.total_api_errors += 1
            self.total_events_fetched += event.events_returned

            # Per-workload stats
            wt = event.workload_type
            if wt not in self.workload_stats:
                self.workload_stats[wt] = {
                    "calls": 0, "events": 0, "errors": 0,
                    "total_latency_ms": 0, "pages": 0,
                }
            stats = self.workload_stats[wt]
            stats["calls"] += 1
            stats["pages"] = max(stats["pages"], event.page)
            stats["events"] += event.events_returned
            stats["total_latency_ms"] += event.latency_ms
            if not event.success:
                stats["errors"] += 1

    def record_rate_limit(self, event: RateLimitEvent) -> None:
        with self._lock:
            self.rate_limits.append(event)
            self.total_rate_limits += 1
            self.total_rate_limit_wait_s += event.retry_after_s

    def start_collection(self) -> None:
        self.collection_start_time = time.time()

    def end_collection(self) -> None:
        self.collection_end_time = time.time()

    @property
    def elapsed_seconds(self) -> float:
        if self.collection_start_time is None:
            return 0
        end = self.collection_end_time or time.time()
        return end - self.collection_start_time

    @property
    def avg_api_latency_ms(self) -> float:
        with self._lock:
            if not self.api_calls:
                return 0
            return sum(c.latency_ms for c in self.api_calls) / len(self.api_calls)

    @property
    def calls_per_second(self) -> float:
        elapsed = self.elapsed_seconds
        if elapsed <= 0:
            return 0
        return self.total_api_calls / elapsed

    def get_summary(self) -> Dict[str, Any]:
        """Get a complete metrics summary."""
        with self._lock:
            recent_refreshes = list(self.token_refreshes)[-5:]
            recent_rate_limits = list(self.rate_limits)[-5:]

        return {
            "collection": {
                "elapsed_seconds": round(self.elapsed_seconds, 1),
                "elapsed_formatted": self._format_duration(self.elapsed_seconds),
                "status": "running" if self.collection_end_time is None else "complete",
            },
            "token": {
                "total_refreshes": self.total_refreshes,
                "refresh_failures": self.total_refresh_failures,
                "recent_refreshes": [
                    {
                        "time": datetime.fromtimestamp(r.timestamp, tz=timezone.utc).isoformat(),
                        "success": r.success,
                        "latency_ms": round(r.latency_ms, 1),
                        "remaining_before_s": round(r.remaining_before_refresh_s, 0),
                    }
                    for r in recent_refreshes
                ],
            },
            "api": {
                "total_calls": self.total_api_calls,
                "total_errors": self.total_api_errors,
                "error_rate_pct": (
                    round(self.total_api_errors / max(1, self.total_api_calls) * 100, 2)
                ),
                "total_events_fetched": self.total_events_fetched,
                "avg_latency_ms": round(self.avg_api_latency_ms, 1),
                "calls_per_second": round(self.calls_per_second, 2),
            },
            "rate_limiting": {
                "total_hits": self.total_rate_limits,
                "total_wait_seconds": round(self.total_rate_limit_wait_s, 1),
                "recent": [
                    {
                        "time": datetime.fromtimestamp(r.timestamp, tz=timezone.utc).isoformat(),
                        "wait_s": r.retry_after_s,
                        "workload": r.workload_type,
                    }
                    for r in recent_rate_limits
                ],
            },
            "workloads": {
                wt: {
                    "calls": s["calls"],
                    "pages": s["pages"],
                    "events": s["events"],
                    "errors": s["errors"],
                    "avg_latency_ms": round(
                        s["total_latency_ms"] / max(1, s["calls"]), 1
                    ),
                }
                for wt, s in self.workload_stats.items()
            },
        }

    @staticmethod
    def _format_duration(seconds: float) -> str:
        s = int(seconds)
        if s < 60:
            return f"{s}s"
        if s < 3600:
            return f"{s // 60}m {s % 60}s"
        return f"{s // 3600}h {(s % 3600) // 60}m {s % 60}s"


# ─────────────────────────────────────────────────────────────────
# Token Monitor (wraps TokenManager + MetricsStore)
# ─────────────────────────────────────────────────────────────────

class TokenMonitor:
    """
    Monitors token health and provides:
    - Real-time metrics collection
    - Configurable alert callbacks
    - Live progress reporting
    - Structured logging
    """

    def __init__(
        self,
        metrics_store: Optional[MetricsStore] = None,
        on_refresh: Optional[Callable[[TokenRefreshEvent], None]] = None,
        on_expiry_warning: Optional[Callable[[float], None]] = None,
        on_failure: Optional[Callable[[str], None]] = None,
        on_rate_limit: Optional[Callable[[RateLimitEvent], None]] = None,
        warning_threshold_seconds: int = 600,
        critical_threshold_seconds: int = 120,
    ):
        self.metrics = metrics_store or MetricsStore()

        # Alert callbacks
        self._on_refresh = on_refresh
        self._on_expiry_warning = on_expiry_warning
        self._on_failure = on_failure
        self._on_rate_limit = on_rate_limit

        # Thresholds
        self._warning_threshold = warning_threshold_seconds
        self._critical_threshold = critical_threshold_seconds

        # State
        self._warning_fired = False
        self._critical_fired = False

    def record_refresh(
        self,
        success: bool,
        latency_ms: float,
        remaining_before: float,
        error: Optional[str] = None,
    ) -> None:
        """Record a token refresh event."""
        event = TokenRefreshEvent(
            timestamp=time.time(),
            success=success,
            latency_ms=latency_ms,
            remaining_before_refresh_s=remaining_before,
            error=error,
            refresh_number=self.metrics.total_refreshes + 1,
        )
        self.metrics.record_token_refresh(event)

        if self._on_refresh:
            self._on_refresh(event)

        if not success and self._on_failure:
            self._on_failure(error or "Unknown refresh failure")

        # Reset warning flags after successful refresh
        if success:
            self._warning_fired = False
            self._critical_fired = False

    def record_api_call(
        self,
        workload_type: str,
        page: int,
        latency_ms: float,
        status_code: int,
        success: bool,
        events_returned: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Record an API call event."""
        event = APICallEvent(
            timestamp=time.time(),
            workload_type=workload_type,
            page=page,
            latency_ms=latency_ms,
            status_code=status_code,
            success=success,
            events_returned=events_returned,
            error=error,
        )
        self.metrics.record_api_call(event)

    def record_rate_limit(
        self, retry_after: int, workload_type: str
    ) -> None:
        """Record a rate limit event."""
        event = RateLimitEvent(
            timestamp=time.time(),
            retry_after_s=retry_after,
            workload_type=workload_type,
        )
        self.metrics.record_rate_limit(event)

        if self._on_rate_limit:
            self._on_rate_limit(event)

    def check_token_health(self, remaining_seconds: float) -> None:
        """
        Check token health and fire alerts if thresholds crossed.
        Call this periodically during collection.
        """
        if remaining_seconds <= self._critical_threshold and not self._critical_fired:
            self._critical_fired = True
            logger.critical(
                f"TOKEN CRITICAL: Only {remaining_seconds:.0f}s remaining!"
            )
            if self._on_expiry_warning:
                self._on_expiry_warning(remaining_seconds)

        elif remaining_seconds <= self._warning_threshold and not self._warning_fired:
            self._warning_fired = True
            logger.warning(
                f"TOKEN WARNING: {remaining_seconds:.0f}s remaining "
                f"(threshold: {self._warning_threshold}s)"
            )
            if self._on_expiry_warning:
                self._on_expiry_warning(remaining_seconds)


# ─────────────────────────────────────────────────────────────────
# Progress Reporter
# ─────────────────────────────────────────────────────────────────

class ProgressReporter:
    """
    Reports progress during long-running collection.
    Supports multiple output modes: logging, callback, structured.
    """

    def __init__(
        self,
        metrics_store: MetricsStore,
        report_interval_seconds: float = 10.0,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self._metrics = metrics_store
        self._interval = report_interval_seconds
        self._callback = callback
        self._last_report_time: float = 0
        self._lock = threading.Lock()

    def maybe_report(self, token_remaining_s: Optional[float] = None) -> None:
        """Report progress if enough time has elapsed since last report."""
        now = time.time()
        if now - self._last_report_time < self._interval:
            return

        with self._lock:
            if now - self._last_report_time < self._interval:
                return
            self._last_report_time = now

        report = self._build_report(token_remaining_s)
        self._emit(report)

    def force_report(self, token_remaining_s: Optional[float] = None) -> None:
        """Force an immediate progress report."""
        report = self._build_report(token_remaining_s)
        self._emit(report)

    def _build_report(self, token_remaining_s: Optional[float]) -> Dict[str, Any]:
        m = self._metrics
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed": m._format_duration(m.elapsed_seconds),
            "api_calls": m.total_api_calls,
            "events_fetched": m.total_events_fetched,
            "errors": m.total_api_errors,
            "rate_limits": m.total_rate_limits,
            "token_refreshes": m.total_refreshes,
            "token_remaining_s": (
                int(token_remaining_s) if token_remaining_s else None
            ),
            "avg_latency_ms": round(m.avg_api_latency_ms, 1),
            "calls_per_second": round(m.calls_per_second, 2),
            "workloads_active": len(m.workload_stats),
        }

    def _emit(self, report: Dict[str, Any]) -> None:
        """Output the progress report."""
        # Log it
        logger.info(
            f"[Progress] "
            f"elapsed={report['elapsed']} "
            f"calls={report['api_calls']} "
            f"events={report['events_fetched']} "
            f"errors={report['errors']} "
            f"token_remaining={report['token_remaining_s']}s "
            f"rate={report['calls_per_second']} calls/s"
        )

        # Callback if provided
        if self._callback:
            self._callback(report)


# ─────────────────────────────────────────────────────────────────
# Console Reporter (for CLI use)
# ─────────────────────────────────────────────────────────────────

class ConsoleReporter:
    """Pretty-prints progress to terminal during test runs."""

    def __init__(self, metrics_store: MetricsStore):
        self._metrics = metrics_store
        self._last_line_len = 0

    def update(self, token_remaining_s: Optional[float] = None) -> None:
        """Print a single-line progress update (overwrites previous)."""
        m = self._metrics
        remaining = f"{int(token_remaining_s)}s" if token_remaining_s else "?"

        line = (
            f"\r⏳ {m._format_duration(m.elapsed_seconds)} | "
            f"📡 {m.total_api_calls} calls | "
            f"📦 {m.total_events_fetched} events | "
            f"❌ {m.total_api_errors} errors | "
            f"🔑 token: {remaining} | "
            f"⚡ {m.calls_per_second:.1f} req/s"
        )

        # Pad with spaces to overwrite previous longer line
        padding = max(0, self._last_line_len - len(line))
        print(line + " " * padding, end="", flush=True)
        self._last_line_len = len(line)

    def final_report(self) -> None:
        """Print final summary after collection completes."""
        print()  # New line after progress updates
        m = self._metrics
        summary = m.get_summary()

        print(f"\n{'='*70}")
        print(f"  COLLECTION METRICS SUMMARY")
        print(f"{'='*70}")
        print(f"  Duration:           {summary['collection']['elapsed_formatted']}")
        print(f"  Total API Calls:    {summary['api']['total_calls']}")
        print(f"  Total Events:       {summary['api']['total_events_fetched']}")
        print(f"  Avg Latency:        {summary['api']['avg_latency_ms']}ms")
        print(f"  Throughput:         {summary['api']['calls_per_second']} calls/s")
        print(f"  Error Rate:         {summary['api']['error_rate_pct']}%")
        print(f"  Token Refreshes:    {summary['token']['total_refreshes']}")
        print(f"  Rate Limit Hits:    {summary['rate_limiting']['total_hits']}")
        print(f"  Rate Limit Wait:    {summary['rate_limiting']['total_wait_seconds']}s")

        if summary["workloads"]:
            print(f"\n  Per-Workload Breakdown:")
            print(f"  {'Type':<35} {'Calls':>6} {'Events':>8} {'Errors':>7} {'Latency':>10}")
            print(f"  {'-'*35} {'-'*6} {'-'*8} {'-'*7} {'-'*10}")
            for wt, stats in sorted(
                summary["workloads"].items(),
                key=lambda x: -x[1]["events"]
            ):
                print(
                    f"  {wt:<35} {stats['calls']:>6} "
                    f"{stats['events']:>8} {stats['errors']:>7} "
                    f"{stats['avg_latency_ms']:>8.1f}ms"
                )

        if summary["token"]["recent_refreshes"]:
            print(f"\n  Token Refresh History:")
            for r in summary["token"]["recent_refreshes"]:
                status = "✅" if r["success"] else "❌"
                print(
                    f"    {status} {r['time'][:19]} "
                    f"latency={r['latency_ms']}ms "
                    f"remaining_before={r['remaining_before_s']}s"
                )

        print(f"{'='*70}")
