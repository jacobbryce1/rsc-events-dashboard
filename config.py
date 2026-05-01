import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()

RSC_SERVICE_ACCOUNT_ID = os.getenv("RSC_SERVICE_ACCOUNT_ID")
RSC_SERVICE_ACCOUNT_SECRET = os.getenv("RSC_SERVICE_ACCOUNT_SECRET")
RSC_BASE_URL = os.getenv("RSC_BASE_URL", "").rstrip("/")
RSC_GRAPHQL_ENDPOINT = f"{RSC_BASE_URL}/api/graphql"
RSC_TOKEN_ENDPOINT = f"{RSC_BASE_URL}/api/client_token"

# ─────────────────────────────────────────────────────────────────
# Types that WORK as activitySeriesConnection objectType filters
# (SCREAMING_SNAKE_CASE only)
# ─────────────────────────────────────────────────────────────────
FILTERABLE_WORKLOAD_TYPES = [
    "K8S_CLUSTER",
    "K8S_PROTECTION_SET",
    "K8S_NAMESPACE_V2",
    "K8S_VIRTUAL_MACHINE",
    "AWS_NATIVE_S3_BUCKET",
    "AWS_NATIVE_DYNAMODB_TABLE",
    "AZURE_STORAGE_ACCOUNT",
    "AZURE_DEVOPS_REPOSITORY",
    "GCP_CLOUD_SQL_INSTANCE",
    "GCP_ALLOY_DB_CLUSTER",
    "CLOUD_DIRECT_NAS_SHARE",
    "MYSQLDB_INSTANCE",
    "M365_BACKUP_STORAGE_ORG",
    "OLVM_MANAGER",
]

# ─────────────────────────────────────────────────────────────────
# Types that appear in event objectType responses (PascalCase)
# but CANNOT be used as filter values. We fetch all events
# unfiltered and match these client-side.
# ─────────────────────────────────────────────────────────────────
UNFILTERABLE_CLOUD_TYPES = [
    "AzureNativeVm",
    "AzureNativeDisk",
    "AzureNativeSubscription",
    "AzureSqlDatabaseServer",
    "AwsNativeAccount",
    "Ec2Instance",
    "GcpNativeGceInstance",
    "GcpNativeProject",
    "Exocompute",
]

# Combined set for client-side matching
ALL_CLOUD_NATIVE_TYPES = set(FILTERABLE_WORKLOAD_TYPES + UNFILTERABLE_CLOUD_TYPES)

# ─────────────────────────────────────────────────────────────────
# Display names for ALL known objectType values
# ─────────────────────────────────────────────────────────────────
WORKLOAD_DISPLAY_NAMES = {
    # Filterable types
    "K8S_CLUSTER": "Kubernetes Cluster",
    "K8S_PROTECTION_SET": "Kubernetes Protection Set",
    "K8S_NAMESPACE_V2": "Kubernetes Namespace",
    "K8S_VIRTUAL_MACHINE": "Kubernetes VM",
    "AWS_NATIVE_S3_BUCKET": "AWS S3 Bucket",
    "AWS_NATIVE_DYNAMODB_TABLE": "AWS DynamoDB Table",
    "AZURE_STORAGE_ACCOUNT": "Azure Storage Account",
    "AZURE_DEVOPS_REPOSITORY": "Azure DevOps Repository",
    "GCP_CLOUD_SQL_INSTANCE": "GCP Cloud SQL Instance",
    "GCP_ALLOY_DB_CLUSTER": "GCP AlloyDB Cluster",
    "CLOUD_DIRECT_NAS_SHARE": "Cloud Direct NAS Share",
    "MYSQLDB_INSTANCE": "MySQL Instance",
    "M365_BACKUP_STORAGE_ORG": "M365 Backup Storage Org",
    "OLVM_MANAGER": "OLVM Manager",
    # Unfilterable PascalCase types
    "AzureNativeVm": "Azure VM",
    "AzureNativeDisk": "Azure Managed Disk",
    "AzureNativeSubscription": "Azure Subscription",
    "AzureSqlDatabaseServer": "Azure SQL Database Server",
    "AwsNativeAccount": "AWS Account",
    "Ec2Instance": "AWS EC2 Instance",
    "GcpNativeGceInstance": "GCP Compute Instance",
    "GcpNativeProject": "GCP Project",
    "Exocompute": "Exocompute",
}

# ─────────────────────────────────────────────────────────────────
# Status mappings — from actual discovered values
# ─────────────────────────────────────────────────────────────────
STATUS_SORT_ORDER = {
    "Running": 0,
    "RUNNING": 0,
    "IN_PROGRESS": 0,
    "ACTIVE": 0,
    "Queued": 1,
    "QUEUED": 1,
    "PENDING": 1,
    "ACQUIRING": 1,
    "Failure": 2,
    "Failed": 2,
    "FAILED": 2,
    "FAILURE": 2,
    "PARTIAL_SUCCESS": 3,
    "Canceled": 3,
    "CANCELED": 3,
    "CANCELLED": 3,
    "Success": 4,
    "TaskSuccess": 4,
    "COMPLETED": 4,
    "SUCCEEDED": 4,
    "SUCCESS": 4,
    "TASK_SUCCESS": 4,
    "Info": 4,
    "INFO": 4,
    "WARNING": 4,
    "Warning": 4,
}

STATUS_CATEGORIES = {
    "Running": "In Progress",
    "RUNNING": "In Progress",
    "IN_PROGRESS": "In Progress",
    "ACTIVE": "In Progress",
    "Queued": "Queued",
    "QUEUED": "Queued",
    "PENDING": "Queued",
    "ACQUIRING": "Queued",
    "Failure": "Failed",
    "Failed": "Failed",
    "FAILED": "Failed",
    "FAILURE": "Failed",
    "PARTIAL_SUCCESS": "Partial",
    "Canceled": "Canceled",
    "CANCELED": "Canceled",
    "CANCELLED": "Canceled",
    "Success": "Completed",
    "TaskSuccess": "Completed",
    "COMPLETED": "Completed",
    "SUCCEEDED": "Completed",
    "SUCCESS": "Completed",
    "TASK_SUCCESS": "Completed",
    "Info": "Completed",
    "INFO": "Completed",
    "WARNING": "Completed",
    "Warning": "Completed",
}


def get_24h_window():
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=24)
    return start.isoformat(), now.isoformat()
