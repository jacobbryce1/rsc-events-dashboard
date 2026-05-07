"""
config.py — Secure configuration loader.

Security fixes applied:
  F-001: urllib3 TLS warning suppression removed entirely (was in rsc_client.py).
  F-002: Credentials wrapped in SecretStr to prevent accidental logging/repr exposure.
  F-004: RSC_BASE_URL validated against allowed pattern at import time.
  F-005: validate_config() raises early with clear errors if any required value is missing.
"""

import os
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()


# ──────────────────────────────────────────────────────────────────────────────
# F-002: SecretStr — wraps credential strings so repr/str never leaks the value
# ──────────────────────────────────────────────────────────────────────────────

class SecretStr:
    """
    A thin wrapper around a string that prevents the value from appearing in
    logs, tracebacks, or repr() output.  Use .get_secret_value() to retrieve
    the actual string — only where the credential is genuinely needed.
    """

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretStr('**********')"

    def __str__(self) -> str:
        return "**********"

    def __bool__(self) -> bool:
        return bool(self._value)

    def __len__(self) -> int:
        return len(self._value)


# ──────────────────────────────────────────────────────────────────────────────
# F-004: URL allowlist pattern — only *.my.rubrik.com over HTTPS is accepted
# ──────────────────────────────────────────────────────────────────────────────

_ALLOWED_URL_RE = re.compile(
    r"^https://[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.my\.rubrik\.com$"
)


def _load_and_validate_base_url() -> str:
    """Load RSC_BASE_URL and validate it strictly.  Raises ValueError on failure."""
    raw = os.getenv("RSC_BASE_URL", "").rstrip("/")
    if not raw:
        raise ValueError(
            "RSC_BASE_URL is not set. "
            "Add it to your .env file: RSC_BASE_URL=https://your-org.my.rubrik.com"
        )
    if not _ALLOWED_URL_RE.match(raw):
        raise ValueError(
            f"RSC_BASE_URL must be of the form https://<org>.my.rubrik.com — "
            f"got: {raw!r}.  "
            "Only HTTPS connections to *.my.rubrik.com are permitted."
        )
    return raw


# ──────────────────────────────────────────────────────────────────────────────
# Credential loading — wrapped in SecretStr (F-002)
# ──────────────────────────────────────────────────────────────────────────────

_raw_id = os.getenv("RSC_SERVICE_ACCOUNT_ID", "")
_raw_secret = os.getenv("RSC_SERVICE_ACCOUNT_SECRET", "")

RSC_SERVICE_ACCOUNT_ID: SecretStr = SecretStr(_raw_id)
RSC_SERVICE_ACCOUNT_SECRET: SecretStr = SecretStr(_raw_secret)

# URL is validated immediately on import (F-004).
# If the URL is invalid the import will raise, giving a fast, clear failure
# before any network connection is attempted.
RSC_BASE_URL: str = _load_and_validate_base_url()

RSC_GRAPHQL_ENDPOINT: str = f"{RSC_BASE_URL}/api/graphql"
RSC_TOKEN_ENDPOINT: str = f"{RSC_BASE_URL}/api/client_token"


# ──────────────────────────────────────────────────────────────────────────────
# F-005: Startup validation — call this once at application entry-point
# ──────────────────────────────────────────────────────────────────────────────

def validate_config() -> None:
    """
    Raise ValueError early if any required credential is missing or obviously
    placeholder-valued.  Call this at the top of dashboard.py before any UI or
    network code runs.
    """
    errors: list[str] = []

    if not RSC_SERVICE_ACCOUNT_ID:
        errors.append(
            "RSC_SERVICE_ACCOUNT_ID is not set. "
            "Add it to your .env file.  "
            "Format: client|xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        )
    elif RSC_SERVICE_ACCOUNT_ID.get_secret_value().startswith("your-"):
        errors.append(
            "RSC_SERVICE_ACCOUNT_ID looks like a placeholder value — "
            "replace it with your real service account ID."
        )

    if not RSC_SERVICE_ACCOUNT_SECRET:
        errors.append(
            "RSC_SERVICE_ACCOUNT_SECRET is not set. "
            "Add it to your .env file."
        )
    elif RSC_SERVICE_ACCOUNT_SECRET.get_secret_value().startswith("your-"):
        errors.append(
            "RSC_SERVICE_ACCOUNT_SECRET looks like a placeholder value — "
            "replace it with your real service account secret."
        )

    if errors:
        raise ValueError(
            "Configuration errors found — cannot start:\n"
            + "\n".join(f"  • {e}" for e in errors)
        )


# ──────────────────────────────────────────────────────────────────────────────
# Tuning constants (unchanged)
# ──────────────────────────────────────────────────────────────────────────────

MAX_WORKERS = 4
FILTERED_PAGE_SIZE = 200
REQUEST_TIMEOUT = 120
INCREMENTAL_PAGE_SIZE = 500
INCREMENTAL_MAX_PAGES = 3

FILTERABLE_WORKLOAD_TYPES = [
    "AWS_NATIVE_EC2_INSTANCE",
    "AWS_NATIVE_EBS_VOLUME",
    "AWS_NATIVE_RDS_INSTANCE",
    "AWS_NATIVE_S3_BUCKET",
    "AWS_NATIVE_DYNAMODB_TABLE",
    "AWS_NATIVE_ACCOUNT",
    "AZURE_NATIVE_VM",
    "AZURE_NATIVE_DISK",
    "AZURE_NATIVE_SUBSCRIPTION",
    "AZURE_SQL_DATABASE",
    "AZURE_SQL_DATABASE_SERVER",
    "AZURE_STORAGE_ACCOUNT",
    "AZURE_DEVOPS_REPOSITORY",
    "GCP_NATIVE_GCE_INSTANCE",
    "GCP_NATIVE_DISK",
    "GCP_NATIVE_PROJECT",
    "GCP_CLOUD_SQL_INSTANCE",
    "GCP_ALLOY_DB_CLUSTER",
    "EXOCOMPUTE",
    "M365_BACKUP_STORAGE_ORG",
]

UNFILTERABLE_CLOUD_TYPES: list = []

ALL_CLOUD_NATIVE_TYPES = set(FILTERABLE_WORKLOAD_TYPES + [
    "AzureNativeVm",
    "AzureNativeDisk",
    "AzureNativeSubscription",
    "AzureSqlDatabaseServer",
    "AzureSqlDatabase",
    "AwsNativeAccount",
    "GcpNativeGceInstance",
    "GcpNativeProject",
    "GcpNativeDisk",
    "Exocompute",
])

WORKLOAD_DISPLAY_NAMES = {
    "AWS_NATIVE_EC2_INSTANCE":    "AWS EC2 Instance",
    "AWS_NATIVE_EBS_VOLUME":      "AWS EBS Volume",
    "AWS_NATIVE_RDS_INSTANCE":    "AWS RDS Instance",
    "AWS_NATIVE_S3_BUCKET":       "AWS S3 Bucket",
    "AWS_NATIVE_DYNAMODB_TABLE":  "AWS DynamoDB Table",
    "AWS_NATIVE_ACCOUNT":         "AWS Account",
    "AwsNativeAccount":           "AWS Account",
    "AZURE_NATIVE_VM":            "Azure VM",
    "AZURE_NATIVE_DISK":          "Azure Managed Disk",
    "AZURE_NATIVE_SUBSCRIPTION":  "Azure Subscription",
    "AZURE_SQL_DATABASE":         "Azure SQL Database",
    "AZURE_SQL_DATABASE_SERVER":  "Azure SQL Database Server",
    "AZURE_STORAGE_ACCOUNT":      "Azure Storage Account",
    "AZURE_DEVOPS_REPOSITORY":    "Azure DevOps Repository",
    "AzureNativeVm":              "Azure VM",
    "AzureNativeDisk":            "Azure Managed Disk",
    "AzureNativeSubscription":    "Azure Subscription",
    "AzureSqlDatabaseServer":     "Azure SQL Database Server",
    "AzureSqlDatabase":           "Azure SQL Database",
    "GCP_NATIVE_GCE_INSTANCE":    "GCP Compute Instance",
    "GCP_NATIVE_DISK":            "GCP Persistent Disk",
    "GCP_NATIVE_PROJECT":         "GCP Project",
    "GCP_CLOUD_SQL_INSTANCE":     "GCP Cloud SQL Instance",
    "GCP_ALLOY_DB_CLUSTER":       "GCP AlloyDB Cluster",
    "GcpNativeGceInstance":       "GCP Compute Instance",
    "GcpNativeProject":           "GCP Project",
    "GcpNativeDisk":              "GCP Persistent Disk",
    "EXOCOMPUTE":                 "Exocompute",
    "Exocompute":                 "Exocompute",
    "M365_BACKUP_STORAGE_ORG":    "M365 Backup Storage Org",
}

STATUS_SORT_ORDER = {
    "Running": 0,  "RUNNING": 0,  "IN_PROGRESS": 0, "ACTIVE": 0,
    "Queued": 1,   "QUEUED": 1,   "PENDING": 1,      "ACQUIRING": 1,
    "Failure": 2,  "Failed": 2,   "FAILED": 2,       "FAILURE": 2,
    "PARTIAL_SUCCESS": 3, "Canceled": 3, "CANCELED": 3, "CANCELLED": 3,
    "Success": 4,  "TaskSuccess": 4, "COMPLETED": 4,  "SUCCEEDED": 4,
    "SUCCESS": 4,  "TASK_SUCCESS": 4, "Info": 4,      "INFO": 4,
    "WARNING": 4,  "Warning": 4,
}

STATUS_CATEGORIES = {
    "Running": "In Progress",     "RUNNING": "In Progress",
    "IN_PROGRESS": "In Progress", "ACTIVE": "In Progress",
    "Queued": "Queued",           "QUEUED": "Queued",
    "PENDING": "Queued",          "ACQUIRING": "Queued",
    "Failure": "Failed",          "Failed": "Failed",
    "FAILED": "Failed",           "FAILURE": "Failed",
    "PARTIAL_SUCCESS": "Partial",
    "Canceled": "Canceled",       "CANCELED": "Canceled", "CANCELLED": "Canceled",
    "Success": "Completed",       "TaskSuccess": "Completed",
    "COMPLETED": "Completed",     "SUCCEEDED": "Completed",
    "SUCCESS": "Completed",       "TASK_SUCCESS": "Completed",
    "Info": "Completed",          "INFO": "Completed",
    "WARNING": "Completed",       "Warning": "Completed",
}


def get_24h_window():
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=24)
    return start.isoformat(), now.isoformat()
