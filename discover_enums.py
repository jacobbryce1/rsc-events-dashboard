# save as: discover_enums.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from rsc_client import RSCClient

client = RSCClient()

# Query the GraphQL schema for the ObjectType enum
query = """
{
    __type(name: "ActivityObjectTypeEnum") {
        enumValues {
            name
            description
        }
    }
}
"""

# Try multiple possible enum type names
enum_names = [
    "ActivityObjectTypeEnum",
    "ObjectTypeEnum", 
    "HierarchyObjectTypeEnum",
    "ManagedObjectType",
    "WorkloadLevelHierarchy",
    "ObjectType",
]

for enum_name in enum_names:
    try:
        q = '{ __type(name: "' + enum_name + '") { enumValues { name description } } }'
        result = client.execute_query(q)
        type_info = result.get("__type")
        
        if type_info and type_info.get("enumValues"):
            print(f"\n✅ Found enum: {enum_name}")
            print(f"   Total values: {len(type_info['enumValues'])}")
            print(f"\n   Cloud-native related values:")
            
            cloud_keywords = [
                "AWS", "AZURE", "GCP", "K8S", "KUBERNETES", 
                "CLOUD", "NATIVE", "EBS", "EC2", "RDS", "S3",
                "VM", "DISK", "SQL", "STORAGE", "EKS", "AKS",
                "GCE", "COMPUTE",
            ]
            
            all_values = []
            for ev in type_info["enumValues"]:
                name = ev["name"]
                all_values.append(name)
                if any(kw in name.upper() for kw in cloud_keywords):
                    desc = ev.get("description") or ""
                    print(f"   • {name}  {desc}")
            
            # Also dump all values to a file for reference
            with open(f"enum_values_{enum_name}.txt", "w") as f:
                for v in sorted(all_values):
                    f.write(v + "\n")
            print(f"\n   All {len(all_values)} values written to enum_values_{enum_name}.txt")
            
    except Exception as e:
        print(f"⬜ {enum_name}: not found ({e})")

# Also try to discover what objectType values actually appear in events
print("\n\n📊 Discovering objectType values from actual events...")
query2 = """
query {
    activitySeriesConnection(first: 100, sortBy: START_TIME, sortOrder: DESC) {
        nodes {
            objectType
        }
    }
}
"""

result = client.execute_query(query2)
nodes = result.get("activitySeriesConnection", {}).get("nodes", [])
types_seen = set()
for node in nodes:
    ot = node.get("objectType")
    if ot:
        types_seen.add(ot)

print(f"   Object types seen in recent events ({len(types_seen)}):")
for t in sorted(types_seen):
    print(f"   • {t}")