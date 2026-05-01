import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from rsc_client import RSCClient
from config import get_24h_window

client = RSCClient()

# ─────────────────────────────────────────────────────────────────
# STEP 1: Pull ALL recent events and see what objectType values
#         the API actually returns. These are the real enum values.
# ─────────────────────────────────────────────────────────────────

print("=" * 70)
print("  DISCOVERING ACTUAL objectType VALUES FROM EVENTS")
print("=" * 70)

start_time, end_time = get_24h_window()

query = """
query($first: Int, $after: String) {
    activitySeriesConnection(
        first: $first,
        after: $after,
        sortBy: START_TIME,
        sortOrder: DESC
    ) {
        nodes {
            objectType
            objectName
            lastActivityType
            lastActivityStatus
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""

all_types = {}
cursor = None
page = 0
total_events = 0

while True:
    page += 1
    variables = {"first": 200, "after": cursor}
    
    result = client.execute_query(query, variables)
    connection = result.get("activitySeriesConnection", {})
    nodes = connection.get("nodes", [])
    page_info = connection.get("pageInfo", {})
    
    for node in nodes:
        total_events += 1
        obj_type = node.get("objectType", "NULL")
        if obj_type not in all_types:
            all_types[obj_type] = {
                "count": 0,
                "sample_name": node.get("objectName"),
                "sample_job": node.get("lastActivityType"),
                "sample_status": node.get("lastActivityStatus"),
            }
        all_types[obj_type]["count"] += 1
    
    print(f"   Page {page}: {len(nodes)} events (total so far: {total_events})")
    
    if page_info.get("hasNextPage") and page_info.get("endCursor"):
        cursor = page_info["endCursor"]
    else:
        break
    
    # Cap at 2000 events to keep it fast
    if total_events >= 2000:
        print(f"   (Stopping at {total_events} events)")
        break

# ─────────────────────────────────────────────────────────────────
# STEP 2: Display all discovered types
# ─────────────────────────────────────────────────────────────────

print(f"\n{'=' * 70}")
print(f"  ALL objectType VALUES FOUND ({len(all_types)} unique types)")
print(f"{'=' * 70}\n")

# Identify cloud-native types
cloud_keywords = [
    "aws", "azure", "gcp", "k8s", "kubernetes", "cloud", "native",
    "ec2", "ebs", "rds", "s3", "dynamodb",
    "vm", "disk", "sql", "storage",
    "gce", "compute", "alloy",
]

cloud_types = []
other_types = []

for obj_type, info in sorted(all_types.items(), key=lambda x: -x[1]["count"]):
    is_cloud = any(kw in obj_type.lower() for kw in cloud_keywords)
    entry = (obj_type, info)
    if is_cloud:
        cloud_types.append(entry)
    else:
        other_types.append(entry)

print("☁️  CLOUD NATIVE TYPES:")
print("-" * 70)
for obj_type, info in cloud_types:
    print(f'   "{obj_type}"')
    print(f"      count={info['count']}, sample={info['sample_name']}, "
          f"job={info['sample_job']}, status={info['sample_status']}")

print(f"\n📦 OTHER TYPES:")
print("-" * 70)
for obj_type, info in other_types:
    print(f'   "{obj_type}"')
    print(f"      count={info['count']}, sample={info['sample_name']}")

# ─────────────────────────────────────────────────────────────────
# STEP 3: Test each discovered cloud type as a filter value
# ─────────────────────────────────────────────────────────────────

print(f"\n{'=' * 70}")
print(f"  TESTING EACH CLOUD TYPE AS A FILTER")
print(f"{'=' * 70}\n")

filter_query = """
query($first: Int, $filters: ActivitySeriesFilter) {
    activitySeriesConnection(first: $first, filters: $filters) {
        nodes { id objectType }
        pageInfo { hasNextPage }
    }
}
"""

working_types = []

for obj_type, info in cloud_types:
    try:
        variables = {
            "first": 1,
            "filters": {
                "objectType": [obj_type],
            },
        }
        result = client.execute_query(filter_query, variables)
        nodes = result.get("activitySeriesConnection", {}).get("nodes", [])
        has_more = result.get("activitySeriesConnection", {}).get("pageInfo", {}).get("hasNextPage", False)
        count_str = "1+" if has_more else str(len(nodes))
        print(f'   ✅ "{obj_type}" works as filter ({count_str} events)')
        working_types.append(obj_type)
    except Exception as e:
        print(f'   ❌ "{obj_type}" FAILS as filter: {e}')

# ─────────────────────────────────────────────────────────────────
# STEP 4: Also test the types from our previous run that worked
# ─────────────────────────────────────────────────────────────────

print(f"\n{'=' * 70}")
print(f"  TESTING PREVIOUSLY KNOWN WORKING TYPES")
print(f"{'=' * 70}\n")

previously_working = [
    "AWS_NATIVE_S3_BUCKET",
    "AWS_NATIVE_DYNAMODB_TABLE",
    "AZURE_STORAGE_ACCOUNT",
    "GCP_CLOUD_SQL_INSTANCE",
    "K8S_CLUSTER",
    "K8S_PROTECTION_SET",
    "K8S_NAMESPACE_V2",
    "K8S_VIRTUAL_MACHINE",
    "GCP_ALLOY_DB_CLUSTER",
]

for obj_type in previously_working:
    if obj_type in working_types:
        continue
    try:
        variables = {
            "first": 1,
            "filters": {
                "objectType": [obj_type],
            },
        }
        result = client.execute_query(filter_query, variables)
        nodes = result.get("activitySeriesConnection", {}).get("nodes", [])
        has_more = result.get("activitySeriesConnection", {}).get("pageInfo", {}).get("hasNextPage", False)
        count_str = "1+" if has_more else str(len(nodes))
        print(f'   ✅ "{obj_type}" works ({count_str} events)')
        working_types.append(obj_type)
    except Exception as e:
        print(f'   ❌ "{obj_type}" FAILS: {e}')

# ─────────────────────────────────────────────────────────────────
# STEP 5: Also discover all statuses
# ─────────────────────────────────────────────────────────────────

print(f"\n{'=' * 70}")
print(f"  ALL STATUS VALUES FOUND")
print(f"{'=' * 70}\n")

all_statuses = {}
for obj_type, info in all_types.items():
    status = info["sample_status"]
    if status not in all_statuses:
        all_statuses[status] = 0
    all_statuses[status] += info["count"]

# Re-scan specifically for statuses
status_query = """
query($first: Int, $after: String) {
    activitySeriesConnection(first: $first, after: $after, sortBy: START_TIME, sortOrder: DESC) {
        nodes { lastActivityStatus }
        pageInfo { hasNextPage endCursor }
    }
}
"""

all_statuses = {}
cursor = None
for _ in range(5):
    variables = {"first": 200, "after": cursor}
    result = client.execute_query(status_query, variables)
    conn = result.get("activitySeriesConnection", {})
    for node in conn.get("nodes", []):
        s = node.get("lastActivityStatus", "NULL")
        all_statuses[s] = all_statuses.get(s, 0) + 1
    pi = conn.get("pageInfo", {})
    if pi.get("hasNextPage") and pi.get("endCursor"):
        cursor = pi["endCursor"]
    else:
        break

for status, count in sorted(all_statuses.items(), key=lambda x: -x[1]):
    print(f'   "{status}": {count}')

# ─────────────────────────────────────────────────────────────────
# STEP 6: Generate the config
# ─────────────────────────────────────────────────────────────────

print(f"\n{'=' * 70}")
print(f"  COPY THIS INTO config.py")
print(f"{'=' * 70}\n")

print("CLOUD_NATIVE_WORKLOAD_TYPES = [")
for wt in working_types:
    print(f'    "{wt}",')
print("]")

print(f"\nTotal working cloud-native filter values: {len(working_types)}")

