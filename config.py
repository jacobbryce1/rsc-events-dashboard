import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()

RSC_SERVICE_ACCOUNT_ID = os.getenv("RSC_SERVICE_ACCOUNT_ID")
RSC_SERVICE_ACCOUNT_SECRET = os.getenv("RSC_SERVICE_ACCOUNT_SECRET")
RSC_BASE_URL = os.getenv("RSC_BASE_URL", "").rstrip("/")
RSC_GRAPHQL_ENDPOINT = f"{RSC_BASE_URL}/api/graphql"
RSC_TOKEN_ENDPOINT = f"{RSC_BASE_URL}/api/client_token"

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

UNFILTERABLE_CLOUD_TYPES = []

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
    "AWS_NATIVE_EC2_INSTANCE": "AWS EC2 Instance",
    "AWS_NATIVE_EBS_VOLUME": "AWS EBS Volume",
    "AWS_NATIVE_RDS_INSTANCE": "AWS RDS Instance",
    "AWS_NATIVE_S3_BUCKET": "AWS S3 Bucket",
    "AWS_NATIVE_DYNAMODB_TABLE": "AWS DynamoDB Table",
    "AWS_NATIVE_ACCOUNT": "AWS Account",
    "AwsNativeAccount": "AWS Account",
    "AZURE_NATIVE_VM": "Azure VM",
    "AZURE_NATIVE_DISK": "Azure Managed Disk",
    "AZURE_NATIVE_SUBSCRIPTION": "Azure Subscription",
    "AZURE_SQL_DATABASE": "Azure SQL Database",
    "AZURE_SQL_DATABASE_SERVER": "Azure SQL Database Server",
    "AZURE_STORAGE_ACCOUNT": "Azure Storage Account",
    "AZURE_DEVOPS_REPOSITORY": "Azure DevOps Repository",
    "AzureNativeVm": "Azure VM",
    "AzureNativeDisk": "Azure Managed Disk",
    "AzureNativeSubscription": "Azure Subscription",
    "AzureSqlDatabaseServer": "Azure SQL Database Server",
    "AzureSqlDatabase": "Azure SQL Database",
    "GCP_NATIVE_GCE_INSTANCE": "GCP Compute Instance",
    "GCP_NATIVE_DISK": "GCP Persistent Disk",
    "GCP_NATIVE_PROJECT": "GCP Project",
    "GCP_CLOUD_SQL_INSTANCE": "GCP Cloud SQL Instance",
    "GCP_ALLOY_DB_CLUSTER": "GCP AlloyDB Cluster",
    "GcpNativeGceInstance": "GCP Compute Instance",
    "GcpNativeProject": "GCP Project",
    "GcpNativeDisk": "GCP Persistent Disk",
    "EXOCOMPUTE": "Exocompute",
    "Exocompute": "Exocompute",
    "M365_BACKUP_STORAGE_ORG": "M365 Backup Storage Org",
}

STATUS_SORT_ORDER = {
    "Running": 0, "RUNNING": 0, "IN_PROGRESS": 0, "ACTIVE": 0,
    "Queued": 1, "QUEUED": 1, "PENDING": 1, "ACQUIRING": 1,
    "Failure": 2, "Failed": 2, "FAILED": 2, "FAILURE": 2,
    "PARTIAL_SUCCESS": 3, "Canceled": 3, "CANCELED": 3, "CANCELLED": 3,
    "Success": 4, "TaskSuccess": 4, "COMPLETED": 4, "SUCCEEDED": 4,
    "SUCCESS": 4, "TASK_SUCCESS": 4, "Info": 4, "INFO": 4,
    "WARNING": 4, "Warning": 4,
}

STATUS_CATEGORIES = {
    "Running": "In Progress", "RUNNING": "In Progress",
    "IN_PROGRESS": "In Progress", "ACTIVE": "In Progress",
    "Queued": "Queued", "QUEUED": "Queued",
    "PENDING": "Queued", "ACQUIRING": "Queued",
    "Failure": "Failed", "Failed": "Failed",
    "FAILED": "Failed", "FAILURE": "Failed",
    "PARTIAL_SUCCESS": "Partial",
    "Canceled": "Canceled", "CANCELED": "Canceled", "CANCELLED": "Canceled",
    "Success": "Completed", "TaskSuccess": "Completed",
    "COMPLETED": "Completed", "SUCCEEDED": "Completed",
    "SUCCESS": "Completed", "TASK_SUCCESS": "Completed",
    "Info": "Completed", "INFO": "Completed",
    "WARNING": "Completed", "Warning": "Completed",
}


def get_24h_window():
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=24)
    return start.isoformat(), now.isoformat()
