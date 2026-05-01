import warnings
import urllib3
warnings.filterwarnings("ignore", category=urllib3.exceptions.NotOpenSSLWarning)

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

logger = logging.getLogger(__name__)


class RSCClient:
    """
    Thread-safe RSC GraphQL client with:
    - Connection pooling (reuses TCP connections)
    - Automatic token refresh (checks before every request)
    - Retry with exponential backoff on transient failures
    - Configurable timeouts
    """

    def __init__(self, max_connections: int = 20, timeout: int = 120):
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._token_lock = threading.Lock()
        self._timeout = timeout

        # ── Connection-pooled session with retry ──
        self._session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,          # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
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
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _authenticate(self) -> None:
        """Obtain a new bearer token. Thread-safe."""
        with self._token_lock:
            # Double-check: another thread may have refreshed while we waited
            if self._token and time.time() < self._token_expiry:
                return

            logger.info("Authenticating with RSC...")
            payload = {
                "client_id": RSC_SERVICE_ACCOUNT_ID,
                "client_secret": RSC_SERVICE_ACCOUNT_SECRET,
            }
            try:
                resp = requests.post(RSC_TOKEN_ENDPOINT, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                self._token = data["access_token"]
                # Refresh 5 minutes before expiry
                self._token_expiry = time.time() + data.get("expires_in", 86400) - 300
                self._session.headers["Authorization"] = f"Bearer {self._token}"
                logger.info("Successfully authenticated with RSC.")
            except requests.RequestException as e:
                logger.error(f"RSC authentication failed: {e}")
                raise

    def _ensure_authenticated(self) -> None:
        """Check token validity before every request. Thread-safe."""
        if self._token is None or time.time() >= self._token_expiry:
            self._authenticate()

    def execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query. Thread-safe."""
        self._ensure_authenticated()

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        req_timeout = timeout or self._timeout

        try:
            resp = self._session.post(
                RSC_GRAPHQL_ENDPOINT, json=payload, timeout=req_timeout
            )

            # Handle rate limiting
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                logger.warning(f"Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                resp = self._session.post(
                    RSC_GRAPHQL_ENDPOINT, json=payload, timeout=req_timeout
                )

            resp.raise_for_status()
            result = resp.json()

            if "errors" in result:
                logger.error(f"GraphQL errors: {result['errors']}")
                raise RuntimeError(f"GraphQL errors: {result['errors']}")

            return result.get("data", {})

        except requests.exceptions.ReadTimeout:
            logger.warning(f"Query timed out after {req_timeout}s — retrying...")
            try:
                resp = self._session.post(
                    RSC_GRAPHQL_ENDPOINT, json=payload, timeout=req_timeout * 2
                )
                resp.raise_for_status()
                result = resp.json()
                if "errors" in result:
                    raise RuntimeError(f"GraphQL errors: {result['errors']}")
                return result.get("data", {})
            except requests.RequestException as e:
                logger.error(f"RSC query failed on retry: {e}")
                raise

        except requests.RequestException as e:
            logger.error(f"RSC query failed: {e}")
            raise

    def execute_paginated_query(
        self,
        query: str,
        variables: Dict[str, Any],
        data_path: str,
        page_size: int = 50,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Paginated fetch with optional page limit.
        Thread-safe — each call manages its own cursor.
        """
        all_nodes = []
        # Deep copy variables so parallel calls don't collide
        local_vars = {k: v for k, v in variables.items()}
        local_vars["first"] = page_size
        local_vars["after"] = None
        page = 0

        while True:
            page += 1
            if max_pages and page > max_pages:
                logger.info(f"Reached max pages ({max_pages}), stopping.")
                break

            data = self.execute_query(query, local_vars)

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
