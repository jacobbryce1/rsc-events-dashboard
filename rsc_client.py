"""
rsc_client.py — RSC GraphQL client with token lifecycle management.

Security fixes applied:
  F-001: Removed urllib3 warning suppression entirely.  Any TLS anomaly will
         now surface as a warning in logs rather than being silently discarded.
  F-002: Credentials are consumed via SecretStr.get_secret_value() only inside
         _do_refresh(), and the payload dict is cleared immediately after the
         POST so the secret does not linger in memory longer than needed.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import threading
import logging
from typing import Optional, Dict, Any, List
from config import (
    RSC_SERVICE_ACCOUNT_ID,
    RSC_SERVICE_ACCOUNT_SECRET,
    RSC_GRAPHQL_ENDPOINT,
    RSC_TOKEN_ENDPOINT,
)
from token_monitor import TokenMonitor, MetricsStore, ProgressReporter

logger = logging.getLogger(__name__)


class RSCClient:
    def __init__(
        self,
        max_connections: int = 20,
        timeout: int = 90,
        monitor: Optional[TokenMonitor] = None,
        metrics: Optional[MetricsStore] = None,
    ):
        self._timeout = timeout
        self._metrics = metrics or MetricsStore()
        self._monitor = monitor or TokenMonitor(metrics_store=self._metrics)
        self._progress = ProgressReporter(self._metrics, report_interval_seconds=15.0)

        # Token state — protected by lock
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._token_lifetime: float = 0
        self._token_lock = threading.Lock()
        self._token_version: int = 0

        # Session for connection pooling only — NO auth header on session
        self._session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=max_connections,
            pool_maxsize=max_connections,
            pool_block=False,
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    @property
    def token_metrics(self) -> Dict[str, Any]:
        return self._metrics.get_summary()

    @property
    def remaining_seconds(self) -> float:
        if not self._token:
            return 0
        return max(0, self._token_expiry - time.time())

    @property
    def needs_refresh(self) -> bool:
        if not self._token:
            return True
        remaining = self.remaining_seconds
        if self._token_lifetime > 0 and remaining / self._token_lifetime < 0.20:
            return True
        return remaining < 300

    def _get_token(self) -> str:
        """Get a valid token, refreshing if needed.  Thread-safe."""
        if not self.needs_refresh and self._token:
            return self._token
        with self._token_lock:
            if not self.needs_refresh and self._token:
                return self._token
            return self._do_refresh()

    def _force_refresh(self) -> str:
        """Force a new token.  Thread-safe."""
        with self._token_lock:
            return self._do_refresh()

    def _do_refresh(self) -> str:
        """
        Perform token refresh.  Must hold _token_lock.

        F-002: Credentials are retrieved via get_secret_value() immediately
        before the POST and the payload dict is deleted right after to minimise
        the window during which the secret lives in a local variable.
        """
        remaining_before = self.remaining_seconds
        start = time.time()

        for attempt in range(1, 4):
            # F-002: build payload inline, clear it immediately after use
            payload = {
                "client_id": RSC_SERVICE_ACCOUNT_ID.get_secret_value(),
                "client_secret": RSC_SERVICE_ACCOUNT_SECRET.get_secret_value(),
            }
            try:
                resp = requests.post(RSC_TOKEN_ENDPOINT, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                self._token = data["access_token"]
                self._token_lifetime = float(data.get("expires_in", 86400))
                self._token_expiry = time.time() + self._token_lifetime
                self._token_version += 1

                latency = (time.time() - start) * 1000
                self._monitor.record_refresh(True, latency, remaining_before)
                logger.info(
                    "Token refreshed (v%d): lifetime=%.0fs, latency=%.0fms",
                    self._token_version, self._token_lifetime, latency,
                )
                return self._token

            except requests.RequestException as e:
                if attempt < 3:
                    wait = 2 ** attempt
                    logger.warning(
                        "Auth attempt %d failed: %s. Retry in %ds…", attempt, e, wait
                    )
                    time.sleep(wait)
                else:
                    latency = (time.time() - start) * 1000
                    self._monitor.record_refresh(False, latency, remaining_before, str(e))
                    raise
            finally:
                # F-002: wipe the payload dict regardless of success/failure
                payload.clear()

        # Should be unreachable but satisfies type-checker
        raise RuntimeError("Token refresh failed after 3 attempts")

    def _make_request(
        self, payload: Dict, timeout: int, token: str
    ) -> requests.Response:
        """
        Make HTTP request with explicit token in headers.
        Does NOT use session-level auth headers — each request carries its own.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        return self._session.post(
            RSC_GRAPHQL_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=timeout,
        )

    def execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        workload_type: str = "general",
        page: int = 0,
    ) -> Dict[str, Any]:
        self._monitor.check_token_health(self.remaining_seconds)

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        req_timeout = timeout or self._timeout
        start = time.time()
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                token = self._get_token()
                resp = self._make_request(payload, req_timeout, token)

                # ── 401 ──────────────────────────────────────────────────────
                if resp.status_code == 401:
                    logger.warning(
                        "401 on attempt %d for %s page %d — forcing refresh…",
                        attempt, workload_type, page,
                    )
                    new_token = self._force_refresh()
                    resp = self._make_request(payload, req_timeout, new_token)
                    if resp.status_code == 401:
                        logger.warning("Still 401 after refresh — waiting 5s…")
                        time.sleep(5)
                        new_token = self._force_refresh()
                        resp = self._make_request(payload, req_timeout, new_token)
                        if resp.status_code == 401:
                            raise RuntimeError(
                                f"Persistent 401 after 2 token refreshes for "
                                f"{workload_type} page {page}"
                            )

                # ── 429 ──────────────────────────────────────────────────────
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 10))
                    self._monitor.record_rate_limit(retry_after, workload_type)
                    logger.warning("Rate limited.  Waiting %ds…", retry_after)
                    time.sleep(retry_after)
                    token = self._get_token()
                    resp = self._make_request(payload, req_timeout, token)

                resp.raise_for_status()
                result = resp.json()

                # ── GraphQL auth errors ───────────────────────────────────────
                if "errors" in result:
                    errors = result["errors"]
                    err_str = str(errors).lower()
                    if "unauthenticated" in err_str or "unauthorized" in err_str:
                        logger.warning("GraphQL auth error — refreshing…")
                        new_token = self._force_refresh()
                        resp = self._make_request(payload, req_timeout, new_token)
                        resp.raise_for_status()
                        result = resp.json()
                        if "errors" in result:
                            raise RuntimeError(
                                f"GraphQL errors after re-auth: {result['errors']}"
                            )
                    else:
                        raise RuntimeError(f"GraphQL errors: {errors}")

                # ── Success ───────────────────────────────────────────────────
                data = result.get("data", {})
                latency = (time.time() - start) * 1000
                events_count = 0
                for key in data:
                    if isinstance(data[key], dict) and "nodes" in data[key]:
                        events_count = len(data[key]["nodes"])
                        break

                self._monitor.record_api_call(
                    workload_type, page, latency, resp.status_code, True, events_count
                )
                self._progress.maybe_report(self.remaining_seconds)
                return data

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.Timeout,
            ) as e:
                latency = (time.time() - start) * 1000
                logger.warning(
                    "Attempt %d/%d for %s page %d: %s",
                    attempt, max_attempts, workload_type, page, type(e).__name__,
                )
                self._monitor.record_api_call(
                    workload_type, page, latency, 0, False, 0, str(e)
                )
                if attempt < max_attempts:
                    wait = min(30, 5 * attempt)
                    logger.info("Waiting %ds before retry…", wait)
                    time.sleep(wait)
                else:
                    raise

            except requests.exceptions.HTTPError as e:
                latency = (time.time() - start) * 1000
                status = e.response.status_code if e.response else 0
                self._monitor.record_api_call(
                    workload_type, page, latency, status, False, 0, str(e)
                )
                if attempt < max_attempts and status in [401, 403]:
                    logger.warning("HTTP %d — refreshing and retrying…", status)
                    self._force_refresh()
                    time.sleep(2)
                else:
                    raise

        raise RuntimeError(
            f"All {max_attempts} attempts failed for {workload_type} page {page}"
        )

    def execute_paginated_query(
        self,
        query: str,
        variables: Dict[str, Any],
        data_path: str,
        page_size: int = 50,
        max_pages: Optional[int] = None,
        workload_type: str = "general",
    ) -> List[Dict[str, Any]]:
        all_nodes: List[Dict[str, Any]] = []
        local_vars = {k: v for k, v in variables.items()}
        local_vars["first"] = page_size
        local_vars["after"] = None
        page = 0

        while True:
            page += 1
            if max_pages and page > max_pages:
                logger.info("Reached max pages (%d) for %s", max_pages, workload_type)
                break

            data = self.execute_query(
                query, local_vars,
                workload_type=workload_type, page=page,
            )

            connection = data
            for key in data_path.split("."):
                connection = connection.get(key, {})

            nodes = connection.get("nodes", [])
            edges = connection.get("edges", [])
            page_info = connection.get("pageInfo", {})

            if edges and not nodes:
                nodes = [edge.get("node", {}) for edge in edges]

            all_nodes.extend(nodes)

            if page_info.get("hasNextPage") and page_info.get("endCursor"):
                local_vars["after"] = page_info["endCursor"]
            else:
                break

        return all_nodes

    def shutdown(self):
        self._session.close()

    def get_progress_report(self) -> Dict[str, Any]:
        return self._metrics.get_summary()

    # Backward compatibility for tests
    def _authenticate(self):
        self._get_token()
