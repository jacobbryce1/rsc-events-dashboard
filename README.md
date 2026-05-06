
# RSC Cloud Native Workload Dashboard

Real-time monitoring dashboard for Rubrik Security Cloud (RSC) job events across all cloud native workloads.

## Overview

This tool connects to your RSC instance via the GraphQL API and provides a rolling 24-hour view of all cloud native protection job events. It features automatic incremental updates, interactive filtering, visual analytics, and data export.

## DISCLAIMER
This project is an independent open-source tool and is not affiliated with, authorized, maintained, sponsored, or endorsed by Rubrik.

## Warranty
This software is provided 'as-is,' without warranty of any kind. Use of this tool is at your own risk. The authors are not responsible for any data loss, API rate-limit overages, or account suspensions resulting from the use of this software.

## Legal
This project is an independent, open-source tool and is not affiliated with, authorized, maintained, sponsored, or endorsed by Rubrik. All product and company names are the registered trademarks of their original owners. The use of any trade name or trademark is for identification and reference purposes only.

## Features

- **Rolling 24-hour view** of all cloud native job events
- **Auto-updating** with incremental fetches (~30 seconds per update)
- **Interactive filtering** by status, workload type, job type, cluster, or text search
- **Quick filter buttons** for Failed Only and Active Only views
- **Visual analytics** - status distribution, workload breakdown, timeline charts
- **Failed jobs detail** - expandable section with error messages
- **CSV/JSON export** of filtered data
- **Disk-cached data** - survives restarts, instant reload from cache
- **Token management** - automatic refresh, retry on failure

## Supported Workloads

| Cloud | Workloads |
|-------|-----------|
| **AWS** | EC2 Instances, EBS Volumes, RDS Instances, S3 Buckets, DynamoDB Tables, Accounts |
| **Azure** | VMs, Managed Disks, Subscriptions, SQL Databases, SQL Database Servers, Storage Accounts, DevOps Repositories |
| **GCP** | Compute Instances, Persistent Disks, Projects, Cloud SQL Instances, AlloyDB Clusters |
| **Other** | Exocompute, M365 Backup Storage |

## Quick Start

### macOS

```bash
# From the package
tar -xzf rsc-cloud-native-dashboard-1.0.0.tar.gz
cd rsc-cloud-native-dashboard-1.0.0
bash install/install_macos.sh
cd ~/rsc-dashboard
./configure.sh
./run.sh

## Linux
tar -xzf rsc-cloud-native-dashboard-1.0.0.tar.gz
cd rsc-cloud-native-dashboard-1.0.0
bash install/install_linux.sh
cd ~/rsc-dashboard
./configure.sh
./run.sh

## Windows (PowerShell)
Expand-Archive rsc-cloud-native-dashboard-1.0.0.zip -DestinationPath .
cd rsc-cloud-native-dashboard-1.0.0
.\install\install_windows.ps1
cd ~\rsc-dashboard
.\configure.bat
.\run.bat

## Prerequisites
| Requirement | Details |
|-------------|---------|
| Python | 3.9 or higher (3.12 recommended) |
| Network | HTTPS access to your RSC instance (port 443) |
| RSC Permissions | Service account with ViewActivity and ViewInventory roles |
| Disk Space | ~100 MB |
| RAM | 512 MB minimum |
To use this tool, you must have a valid API key and an active subscription/license for Rubrik Security Cloud (RSC). This software does not bypass any licensing checks or provide unauthorized access to Rubrik features.

## Configuration
Create a .env file with your RSC service account credentials:
RSC_SERVICE_ACCOUNT_ID=client|xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
RSC_SERVICE_ACCOUNT_SECRET=your-secret-here
RSC_BASE_URL=https://your-org.my.rubrik.com

⚠️ Security Notice: Never commit your API keys to version control. This project supports .env files for local development. See the .env.example for the required format."

Or run the interactive configuration:
./configure.sh

## RSC Service Account Setup
1. Log into RSC > Settings > Service Accounts
2. Create a new service account
3. Assign roles: ViewActivity and ViewInventory
4. Copy the Client ID and Secret into your .env file

## Usage
Starting the Dashboard
cd ~/rsc-dashboard
./run.sh

Opens http://localhost:8501 in your browser.

## What to Expect
First launch: Full 24h scan takes 3-5 minutes
Subsequent visits: Loads from cache instantly, incremental updates in ~30s
Auto-refresh: Toggle in sidebar, configurable interval (15s-5m)

## Dashboard Controls
| Control | Action |
|---------|--------|
| Update | Fetch new events since last update |
| Full Reload | Clear cache, rescan full 24 hours |
| Auto-refresh | Toggle automatic periodic updates |
| Interval | Time between auto-refreshes |

## Filters
| Filter | Description |
|--------|-------------|
| Status | In Progress, Queued, Failed, Partial, Canceled, Completed |
| Workload Type | AWS EC2, Azure VM, GCP Compute, etc. |
| Job Type | Backup, Replication, Archive, Recovery, etc. |
| Cluster | RSC cluster (if multiple) |
| Search | Free-text search on object name or ID |
| Quick: Failed | One-click show only failed/partial |
| Quick: Active | One-click show only in-progress/queued |

## Testing
Validate connectivity and data collection:
cd ~/rsc-dashboard
./test.sh

## Architecture
RSC GraphQL API (activitySeriesConnection)
         |
         | 20 filtered queries (4 parallel)
         v
+---------------------------+
|   EventDataCollector       |
|   - Token management       |
|   - Retry on failure       |
|   - Progress reporting     |
+-------------+-------------+
              |
              v
+---------------------------+
|   IncrementalCache         |
|   - Rolling 24h window     |
|   - Merge new/updated      |
|   - Expire old events      |
|   - Persist to disk        |
+-------------+-------------+
              |
              v
+---------------------------+
|   Streamlit Dashboard      |
|   - KPIs and charts        |
|   - Filters and search     |
|   - Auto-refresh           |
|   - CSV/JSON export        |
+---------------------------+

## Project Structure
rsc-dashboard/
|-- dashboard.py           # Streamlit UI
|-- data_collector.py      # RSC API event fetching
|-- rsc_client.py          # GraphQL client with token management
|-- incremental_cache.py   # Rolling 24h cache with disk persistence
|-- token_monitor.py       # Token health metrics
|-- config.py              # Configuration and workload type mappings
|-- utils.py               # DataFrame helpers
|-- requirements.txt       # Python dependencies
|-- .env                   # RSC credentials (not committed)
|-- .event_cache.json      # Cached event data (auto-generated)
|-- assets/                # Images
|-- tests/                 # Validation test suite
|-- docs/                  # Setup guide and troubleshooting
|-- install/               # OS-specific install scripts

## Performance
| Operation | Duration |
|-----------|----------|
| Full 24h load | 3-5 minutes |
| Incremental update | ~30 seconds |
| Dashboard restart (cached) | < 5 seconds |
The RSC API responds in ~30-40 seconds per request. The dashboard uses 4 parallel workers which balances speed against server-side throttling.

## Documentation
Setup Guide - Full installation and configuration instructions
Troubleshooting - Common issues and solutions

## Updating
cd ~/rsc-dashboard
source .venv/bin/activate
# Copy new .py files over existing ones
pip install -r requirements.txt
rm -f .event_cache.json
./run.sh

## Uninstalling
rm -rf ~/rsc-dashboard